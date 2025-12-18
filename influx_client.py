"""InfluxDB time-series client integration.

This module provides a thin wrapper around the InfluxDB Python client so that
the rest of the codebase can write/query time-series data without depending
directly on Influx-specific details.

Design goals:
- Optional: if InfluxDB is not configured or not reachable, all operations
  become no-ops and the rest of the platform continues to work using PostgreSQL.
- Simple: we focus on the core use-cases needed by this project:
  - writing flattened numeric telemetry fields
  - querying recent history for a single device + key
- Retention-aware: we support three logical tiers mapped to Influx buckets:
  - "hot"  (30 days)    → high-frequency, recent queries
  - "warm" (1 year)     → medium-term analytics
  - "cold" (5+ years)   → long-term archive (configurable, default infinite)
"""

import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List

from config import settings

logger = logging.getLogger(__name__)

try:
    from influxdb_client import InfluxDBClient, Point, BucketRetentionRules
    from influxdb_client.client.write_api import SYNCHRONOUS
    from influxdb_client.client.exceptions import InfluxDBError

    INFLUX_AVAILABLE = True
except Exception:  # pragma: no cover - handled gracefully at runtime
    InfluxDBClient = None  # type: ignore
    Point = None  # type: ignore
    BucketRetentionRules = None  # type: ignore
    InfluxDBError = Exception  # type: ignore
    SYNCHRONOUS = None  # type: ignore
    INFLUX_AVAILABLE = False
    logger.warning("influxdb-client not installed; InfluxDB integration disabled.")


def _flatten_numeric_fields(payload: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
    """Flatten a nested payload to a dict of numeric fields.

    Example:
        {"battery": {"soc": 83}, "temperature": 24.5}
        → {"battery.soc": 83.0, "temperature": 24.5}
    """
    flat: Dict[str, float] = {}
    for key, value in payload.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, (int, float)):
            flat[full_key] = float(value)
        elif isinstance(value, dict):
            flat.update(_flatten_numeric_fields(value, full_key))
    return flat


class InfluxService:
    """Wrapper around InfluxDBClient with sensible defaults for this project."""

    def __init__(self) -> None:
        self._enabled = False
        self._client = None
        self._write_api = None
        self._query_api = None

        if not INFLUX_AVAILABLE:
            logger.info("InfluxDB client not available; skipping initialization.")
            return

        url = settings.influx_url
        token = settings.influx_token
        org = settings.influx_org

        if not token:
            logger.info("INFLUXDB_TOKEN not set; InfluxDB integration disabled.")
            return

        try:
            self._client = InfluxDBClient(url=url, token=token, org=org, timeout=10_000)
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self._query_api = self._client.query_api()
            self._enabled = True
            logger.info("InfluxDB client initialized: url=%s, org=%s", url, org)

            # Optionally ensure buckets with retention policies exist
            self._ensure_buckets()
        except Exception as exc:  # pragma: no cover - network / config dependent
            logger.warning("Failed to initialize InfluxDB client: %s", exc)
            self._enabled = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    # ------------------------------------------------------------------
    # Bucket management
    # ------------------------------------------------------------------
    def _ensure_buckets(self) -> None:
        """Ensure hot/warm/cold buckets exist with configured retention policies.

        This runs best-effort; if bucket creation fails, we log a warning and
        continue, letting writes fail gracefully later if needed.
        """
        if not self._client:
            return

        try:
            buckets_api = self._client.buckets_api()
        except Exception as exc:  # pragma: no cover
            logger.debug("Unable to access Influx buckets API: %s", exc)
            return

        org = settings.influx_org
        existing = {b.name for b in buckets_api.find_buckets().buckets or []}  # type: ignore[attr-defined]

        def _create_bucket_if_missing(name: str, retention_days: int) -> None:
            if name in existing:
                return
            try:
                if retention_days > 0:
                    rules = BucketRetentionRules(
                        type="expire", every_seconds=retention_days * 24 * 3600
                    )
                    buckets_api.create_bucket(
                        bucket_name=name,
                        org=org,
                        retention_rules=rules,
                    )
                else:
                    # 0 days → infinite retention (suitable for 5+ years cold storage)
                    buckets_api.create_bucket(bucket_name=name, org=org)
                logger.info(
                    "Created InfluxDB bucket '%s' with retention_days=%s",
                    name,
                    retention_days,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Failed to create InfluxDB bucket '%s': %s", name, exc
                )

        _create_bucket_if_missing(settings.influx_bucket_hot, settings.influx_hot_retention_days)
        _create_bucket_if_missing(settings.influx_bucket_warm, settings.influx_warm_retention_days)
        _create_bucket_if_missing(settings.influx_bucket_cold, settings.influx_cold_retention_days)

    # ------------------------------------------------------------------
    # Write APIs
    # ------------------------------------------------------------------
    def write_telemetry(
        self,
        device_id: str,
        tenant_id: int,
        payload: Dict[str, Any],
        event_ts: datetime,
    ) -> None:
        """Write a telemetry payload for a device into hot/warm/cold buckets.

        We write into all three buckets so that:
          - Hot bucket keeps ~30 days
          - Warm bucket keeps ~1 year
          - Cold bucket keeps 5+ years (effectively infinite retention)

        This avoids the need for complex cross-bucket migration logic while
        still providing clear retention tiers for different query patterns.
        """
        if not self._enabled or not self._write_api or not self._client:
            return

        fields = _flatten_numeric_fields(payload)
        if not fields:
            # Nothing numeric to store; skip
            return

        # Build a single measurement with multiple fields for efficient storage
        try:
            point = (
                Point(settings.influx_measurement_name)
                .tag("device_id", device_id)
                .tag("tenant_id", str(tenant_id))
                .time(event_ts)
            )
            for key, value in fields.items():
                point = point.field(key, value)

            # Write to all three buckets (hot/warm/cold)
            for bucket in (
                settings.influx_bucket_hot,
                settings.influx_bucket_warm,
                settings.influx_bucket_cold,
            ):
                try:
                    self._write_api.write(bucket=bucket, org=settings.influx_org, record=point)
                except InfluxDBError as exc:  # pragma: no cover - runtime only
                    logger.warning(
                        "InfluxDB write failed for bucket=%s, device_id=%s: %s",
                        bucket,
                        device_id,
                        exc,
                    )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to prepare InfluxDB point for device_id=%s: %s", device_id, exc)

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------
    def query_device_history(
        self,
        device_id: str,
        key: str,
        minutes: int,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Query time-series history for a device/key from the appropriate tier.

        - Minutes <= hot window → hot bucket
        - Minutes <= warm window → warm bucket
        - Otherwise              → cold bucket
        """
        if not self._enabled or not self._query_api:
            return []

        # Choose bucket based on lookback window
        minutes_in_day = 24 * 60
        if minutes <= settings.influx_hot_retention_days * minutes_in_day:
            bucket = settings.influx_bucket_hot
        elif minutes <= settings.influx_warm_retention_days * minutes_in_day:
            bucket = settings.influx_bucket_warm
        else:
            bucket = settings.influx_bucket_cold

        start_range = f"-{minutes}m"

        # Flux query to fetch the field history
        query = f"""
from(bucket: "{bucket}")
  |> range(start: {start_range})
  |> filter(fn: (r) => r["_measurement"] == "{settings.influx_measurement_name}")
  |> filter(fn: (r) => r["device_id"] == "{device_id}")
  |> filter(fn: (r) => r["_field"] == "{key}")
  |> sort(columns: ["_time"])
  |> limit(n: {limit})
"""

        try:
            tables = self._query_api.query(query=query, org=settings.influx_org)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "InfluxDB query failed for device_id=%s, key=%s: %s",
                device_id,
                key,
                exc,
            )
            return []

        points: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                val = record.get_value()
                if ts is not None:
                    points.append({"ts": ts.isoformat(), "value": val})
        return points

    # ------------------------------------------------------------------
    # Introspection / admin helpers
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        """Return basic InfluxDB status and bucket retention information.

        This is used by admin endpoints to verify that the three-tier
        (hot / warm / cold) storage is correctly configured.
        """
        base: Dict[str, Any] = {
            "enabled": bool(self._enabled),
            "url": settings.influx_url,
            "org": settings.influx_org,
            "buckets": [],
        }

        if not self._enabled or not self._client:
            # When disabled, just return configuration + enabled flag
            return base

        try:
            buckets_api = self._client.buckets_api()
            buckets = buckets_api.find_buckets().buckets or []  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to fetch InfluxDB buckets: %s", exc)
            base["error"] = str(exc)
            return base

        bucket_infos: List[Dict[str, Any]] = []
        for b in buckets:
            # Each bucket can have zero or more retention rules; we care about the first
            retention_seconds = None
            retention_days = None
            rule_type = None
            try:
                rules = getattr(b, "retention_rules", None) or []
                if rules:
                    rule = rules[0]
                    rule_type = getattr(rule, "type", None)
                    every_seconds = getattr(rule, "every_seconds", None)
                    if every_seconds is not None:
                        retention_seconds = int(every_seconds)
                        retention_days = round(retention_seconds / 86400, 2)
            except Exception:
                # Best-effort; leave retention fields as None if anything goes wrong
                pass

            bucket_infos.append(
                {
                    "id": getattr(b, "id", None),
                    "name": getattr(b, "name", None),
                    "description": getattr(b, "description", None),
                    "retention_seconds": retention_seconds,
                    "retention_days": retention_days,
                    "rule_type": rule_type,
                }
            )

        base["buckets"] = bucket_infos
        return base

    def get_bucket_sample(self, bucket: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return a small sample of recent points from a given bucket.

        This is purely for admin/debugging purposes so that you can confirm the
        bucket is receiving data. The query is intentionally simple.
        """
        if not self._enabled or not self._query_api:
            return []

        # Look back over the last 1 hour for any telemetry measurement
        query = f"""
from(bucket: "{bucket}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "{settings.influx_measurement_name}")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
"""

        try:
            tables = self._query_api.query(query=query, org=settings.influx_org)
        except Exception as exc:  # pragma: no cover
            logger.warning("InfluxDB sample query failed for bucket=%s: %s", bucket, exc)
            return []

        items: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                if ts is None:
                    continue
                items.append(
                    {
                        "bucket": bucket,
                        "time": ts.isoformat(),
                        "measurement": record.get_measurement(),
                        "field": record.get_field(),
                        "device_id": record.values.get("device_id"),
                        "value": record.get_value(),
                    }
                )

        return items


# Global singleton used across the application
influx_service = InfluxService()


