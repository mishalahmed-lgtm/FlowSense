"""SmartLPG utility billing report generation from Firestore + schedule helpers."""
from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCHEDULE_COLLECTION = "smartLPG_utility_billing_schedule"
SCHEDULE_DOC_ID = "config"
SMARTLPG_DEVICES_COLLECTION = "smartLPG"

TANK_CAPACITY_LITERS = 1000.0
COST_PER_LITER_AED = 3.0

FREQUENCY_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


def _device_seed(device_id: str) -> int:
    return sum(ord(c) for c in (device_id or ""))


def calculate_gas_consumption(device: Dict[str, Any]) -> Dict[str, Any]:
    """Match frontend smartLPGDataMapper.calculateGasConsumption logic."""
    td = {}
    telem = device.get("telemetry") or {}
    if isinstance(telem, dict):
        td = telem.get("data") or {}
    level_percent = float(td.get("level_percent") or device.get("level_percent") or 0)
    current_liters = (level_percent / 100.0) * TANK_CAPACITY_LITERS
    consumed_percent = 100.0 - level_percent
    consumed_liters = (consumed_percent / 100.0) * TANK_CAPACITY_LITERS
    consumption_cost = consumed_liters * COST_PER_LITER_AED
    device_id = str(device.get("device_id") or "")
    random_factor = (_device_seed(device_id) % 100) / 100.0
    monthly_consumption_liters = 200.0 + (random_factor * 600.0)
    monthly_cost = monthly_consumption_liters * COST_PER_LITER_AED
    return {
        "monthly_consumption_liters": monthly_consumption_liters,
        "monthly_cost_aed": monthly_cost,
    }


def _parse_iso_date(s: str) -> date:
    return date.fromisoformat(s[:10])


def report_period_for_frequency(frequency: str, end: datetime) -> Tuple[str, str]:
    """Return (from_date, to_date) as YYYY-MM-DD strings for the report window."""
    days = FREQUENCY_DAYS.get(frequency, 30)
    end_d = end.date()
    start_d = end_d - timedelta(days=days)
    return start_d.isoformat(), end_d.isoformat()


def rows_per_device(
    devices: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
    tenant_id: int = 3,
) -> List[Dict[str, Any]]:
    fd = _parse_iso_date(from_date)
    td = _parse_iso_date(to_date)
    days_diff = max(1, (td - fd).days)
    rows = []
    for device in devices:
        consumption = calculate_gas_consumption(device)
        period_consumption = (float(consumption["monthly_consumption_liters"]) / 30.0) * days_diff
        period_cost = (float(consumption["monthly_cost_aed"]) / 30.0) * days_diff
        did = device.get("device_id") or device.get("id") or ""
        name = device.get("name") or device.get("device_name") or did
        rows.append(
            {
                "tenant_id": tenant_id,
                "tenant_name": "SmartLPG",
                "device_id": did,
                "device_external_id": did,
                "device_name": name,
                "utility_kind": "gas",
                "index_key": "lpg_tank_level",
                "period_start": from_date,
                "period_end": to_date,
                "consumption": round(period_consumption, 2),
                "unit": "L",
                "rate_per_unit": COST_PER_LITER_AED,
                "currency": "AED",
                "amount": round(period_cost, 2),
            }
        )
    return rows


def rows_consolidated(
    devices: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
    tenant_id: int = 3,
) -> List[Dict[str, Any]]:
    fd = _parse_iso_date(from_date)
    td = _parse_iso_date(to_date)
    days_diff = max(1, (td - fd).days)
    total_consumption = 0.0
    total_cost = 0.0
    for device in devices:
        consumption = calculate_gas_consumption(device)
        total_consumption += (float(consumption["monthly_consumption_liters"]) / 30.0) * days_diff
        total_cost += (float(consumption["monthly_cost_aed"]) / 30.0) * days_diff
    return [
        {
            "tenant_id": tenant_id,
            "tenant_name": "SmartLPG",
            "utility_kind": "gas",
            "period_start": from_date,
            "period_end": to_date,
            "total_consumption": round(total_consumption, 2),
            "unit": "L",
            "total_cost": round(total_cost, 2),
            "currency": "AED",
            "device_count": len(devices),
        }
    ]


def build_html_email(
    report_kind: str,
    from_date: str,
    to_date: str,
    per_device_rows: List[Dict[str, Any]],
    consolidated_rows: List[Dict[str, Any]],
) -> str:
    title = (
        "SmartLPG — Per-device utility billing"
        if report_kind == "per_device"
        else "SmartLPG — Consolidated utility billing"
    )
    parts = [
        f"<html><head><meta charset='utf-8'><title>{title}</title>",
        "<style>body{font-family:system-ui,sans-serif;color:#111;line-height:1.5;}",
        "table{border-collapse:collapse;width:100%;max-width:720px;margin:16px 0;}",
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;}",
        "th{background:#f4f4f5;}</style></head><body>",
        f"<h2>{title}</h2>",
        f"<p><strong>Period:</strong> {from_date} to {to_date}</p>",
    ]
    if report_kind == "per_device" and per_device_rows:
        parts.append("<table><thead><tr><th>Device</th><th>Consumption (L)</th><th>Amount (AED)</th></tr></thead><tbody>")
        for r in per_device_rows:
            parts.append(
                f"<tr><td>{_esc(r.get('device_name'))}<br/><small>{_esc(r.get('device_id'))}</small></td>"
                f"<td>{r.get('consumption', 0):.2f}</td><td>{r.get('amount', 0):.2f}</td></tr>"
            )
        parts.append("</tbody></table>")
    elif consolidated_rows:
        r = consolidated_rows[0]
        parts.append(
            "<table><tbody>"
            f"<tr><th>Total devices</th><td>{r.get('device_count', 0)}</td></tr>"
            f"<tr><th>Total consumption (L)</th><td>{r.get('total_consumption', 0):.2f}</td></tr>"
            f"<tr><th>Total amount (AED)</th><td>{r.get('total_cost', 0):.2f}</td></tr>"
            "</tbody></table>"
        )
    else:
        parts.append("<p>No billing rows generated.</p>")
    parts.append("<p style='color:#666;font-size:12px;'>This message was sent automatically by the FlowSense SmartLPG billing scheduler.</p>")
    parts.append("</body></html>")
    return "".join(parts)


def _esc(s: Any) -> str:
    if s is None:
        return ""
    t = str(s)
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def normalize_recipient_emails(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,;\s]+", raw.strip())
        return [p.strip().lower() for p in parts if p.strip() and "@" in p]
    if isinstance(raw, list):
        out = []
        for x in raw:
            if isinstance(x, str) and "@" in x:
                out.append(x.strip().lower())
        return out
    return []


def _to_utc_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if hasattr(val, "timestamp"):
        try:
            return datetime.fromtimestamp(val.timestamp(), tz=timezone.utc)
        except Exception:
            pass
    if isinstance(val, str):
        try:
            s = val.replace("Z", "+00:00")
            return datetime.fromisoformat(s).astimezone(timezone.utc)
        except Exception:
            pass
    return None


def compute_next_send_after(
    frequency: str,
    after: datetime,
    send_hour_utc: int,
    send_minute_utc: int,
    day_of_week: int = 0,
    day_of_month: int = 1,
) -> datetime:
    """
    Next scheduled send strictly after `after` (UTC).
    day_of_week: Monday=0 .. Sunday=6 (datetime.weekday()).
    """
    hour = max(0, min(23, int(send_hour_utc)))
    minute = max(0, min(59, int(send_minute_utc)))
    dow = max(0, min(6, int(day_of_week)))
    dom = max(1, min(28, int(day_of_month)))

    if frequency == "weekly":
        base = after.replace(second=0, microsecond=0)
        days_ahead = (dow - base.weekday()) % 7
        cand = base + timedelta(days=days_ahead)
        cand = cand.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if cand <= after:
            cand += timedelta(days=7)
        return cand.astimezone(timezone.utc)

    if frequency == "monthly":
        return _next_monthly_occurrence(after, dom, hour, minute)

    if frequency == "quarterly":
        return _next_quarterly_occurrence(after, dom, hour, minute)

    if frequency == "yearly":
        return _next_yearly_occurrence(after, dom, hour, minute)

    # fallback = monthly
    return _next_monthly_occurrence(after, dom, hour, minute)


def _next_monthly_occurrence(after: datetime, dom: int, hour: int, minute: int) -> datetime:
    y, m = after.year, after.month
    for step in range(0, 40):
        total_m = m + step
        yy = y + (total_m - 1) // 12
        mm = ((total_m - 1) % 12) + 1
        last = calendar.monthrange(yy, mm)[1]
        dd = min(dom, last)
        cand = datetime(yy, mm, dd, hour, minute, 0, tzinfo=timezone.utc)
        if cand > after:
            return cand
    return after + timedelta(days=32)


def _next_quarterly_occurrence(after: datetime, dom: int, hour: int, minute: int) -> datetime:
    current = datetime(after.year, after.month, 1, tzinfo=timezone.utc)
    for _ in range(48):
        y, m = current.year, current.month
        if m in (1, 4, 7, 10):
            last = calendar.monthrange(y, m)[1]
            dd = min(dom, last)
            try:
                cand = datetime(y, m, dd, hour, minute, 0, tzinfo=timezone.utc)
            except ValueError:
                cand = None
            else:
                if cand > after:
                    return cand
        ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
        current = datetime(ny, nm, 1, tzinfo=timezone.utc)
    return after + timedelta(days=100)


def _next_yearly_occurrence(after: datetime, dom: int, hour: int, minute: int) -> datetime:
    for y in range(after.year, after.year + 6):
        last = calendar.monthrange(y, 1)[1]
        dd = min(dom, last)
        try:
            cand = datetime(y, 1, dd, hour, minute, 0, tzinfo=timezone.utc)
        except ValueError:
            continue
        if cand > after:
            return cand
    return after + timedelta(days=400)
