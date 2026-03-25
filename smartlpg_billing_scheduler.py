"""Background worker: send scheduled SmartLPG utility billing reports by email."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from notification_service import notification_service
from services.firebase_service import get_firestore_client
from services.smartlpg_billing_report import (
    SCHEDULE_COLLECTION,
    SCHEDULE_DOC_ID,
    SMARTLPG_DEVICES_COLLECTION,
    build_html_email,
    compute_next_send_after,
    normalize_recipient_emails,
    report_period_for_frequency,
    rows_consolidated,
    rows_per_device,
    _to_utc_datetime,
)

logger = logging.getLogger(__name__)


def _fetch_smartlpg_devices() -> List[Dict[str, Any]]:
    db = get_firestore_client()
    out: List[Dict[str, Any]] = []
    for doc in db.collection(SMARTLPG_DEVICES_COLLECTION).stream():
        data = doc.to_dict() or {}
        data["_doc_id"] = doc.id
        device_id = data.get("device_id") or data.get("valve_id") or data.get("gateway_id") or doc.id
        data["device_id"] = device_id
        out.append(data)
    return out


def _get_schedule() -> Optional[Dict[str, Any]]:
    try:
        db = get_firestore_client()
        snap = db.collection(SCHEDULE_COLLECTION).document(SCHEDULE_DOC_ID).get()
        if not snap.exists:
            return None
        return snap.to_dict()
    except Exception as e:
        logger.debug("SmartLPG billing schedule read skipped: %s", e)
        return None


def _save_schedule_update(updates: Dict[str, Any]) -> None:
    db = get_firestore_client()
    ref = db.collection(SCHEDULE_COLLECTION).document(SCHEDULE_DOC_ID)
    ref.set(updates, merge=True)


def run_smartlpg_billing_send_if_due() -> None:
    """Load schedule from Firestore; if due, build report and email recipients."""
    schedule: Optional[Dict[str, Any]] = None
    try:
        schedule = _get_schedule()
    except Exception as e:
        logger.warning("Could not read SmartLPG billing schedule: %s", e)
        return

    if not schedule or not schedule.get("enabled"):
        return

    recipients = normalize_recipient_emails(schedule.get("recipient_emails"))
    if not recipients:
        logger.warning("SmartLPG billing schedule enabled but no recipient_emails")
        return

    frequency = (schedule.get("frequency") or "monthly").lower()
    if frequency not in ("weekly", "monthly", "quarterly", "yearly"):
        frequency = "monthly"

    report_kind = (schedule.get("report_kind") or "consolidated").lower()
    if report_kind not in ("per_device", "consolidated"):
        report_kind = "consolidated"

    send_hour = int(schedule.get("send_hour_utc", 6))
    send_minute = int(schedule.get("send_minute_utc", 0))
    day_of_week = int(schedule.get("day_of_week", 0))
    day_of_month = int(schedule.get("day_of_month", 1))

    now = datetime.now(timezone.utc)
    next_send = _to_utc_datetime(schedule.get("next_send_at"))
    if not next_send:
        anchor = now - timedelta(seconds=1)
        next_first = compute_next_send_after(
            frequency, anchor, send_hour, send_minute, day_of_week, day_of_month
        )
        if next_first <= now:
            next_first = compute_next_send_after(
                frequency, now, send_hour, send_minute, day_of_week, day_of_month
            )
        try:
            _save_schedule_update({"next_send_at": next_first})
        except Exception:
            pass
        logger.debug("SmartLPG billing: initialized next_send_at to %s", next_first.isoformat())
        return

    if now < next_send:
        return

    try:
        devices = _fetch_smartlpg_devices()
    except Exception as e:
        logger.error("SmartLPG billing: failed to load devices: %s", e, exc_info=True)
        return

    from_d, to_d = report_period_for_frequency(frequency, now)
    if report_kind == "per_device":
        per_rows = rows_per_device(devices, from_d, to_d)
        cons_rows = []
    else:
        per_rows = []
        cons_rows = rows_consolidated(devices, from_d, to_d)

    html = build_html_email(report_kind, from_d, to_d, per_rows, cons_rows)
    subject = f"SmartLPG utility billing ({frequency}) — {from_d} to {to_d}"

    ok = notification_service.send_html_email(
        recipients,
        subject,
        html,
        text_body=f"SmartLPG billing report for {from_d} to {to_d}. Open this message in HTML view.",
    )
    if not ok:
        logger.warning("SmartLPG billing email not sent (SMTP missing or error); not advancing schedule")
        return

    next_after = compute_next_send_after(
        frequency,
        now,
        send_hour,
        send_minute,
        day_of_week,
        day_of_month,
    )
    try:
        _save_schedule_update(
            {
                "last_sent_at": now,
                "next_send_at": next_after,
                "last_error": None,
            }
        )
    except Exception as e:
        logger.error("SmartLPG billing: failed to persist schedule after send: %s", e)


class SmartLPGBillingScheduler:
    """Runs billing email checks on a background thread."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            logger.warning("SmartLPG billing scheduler already running")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("SmartLPG billing scheduler started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("SmartLPG billing scheduler stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                run_smartlpg_billing_send_if_due()
            except Exception as e:
                logger.error("SmartLPG billing scheduler error: %s", e, exc_info=True)
            time.sleep(60)


smartlpg_billing_scheduler = SmartLPGBillingScheduler()
