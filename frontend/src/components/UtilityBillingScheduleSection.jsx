import { useEffect, useState } from "react";
import Icon from "./Icon.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { isSmartLPGTenant } from "../utils/tenantHelpers.js";
import {
  getUtilityBillingScheduleFromFirebase,
  saveUtilityBillingScheduleToFirebase,
} from "../services/smartLPGFirebaseService.js";

const FREQUENCIES = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

const WEEKDAYS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
  { value: 6, label: "Sunday" },
];

/** SmartLPG billing reports recipient (administrative default; saved with every schedule). */
const SMARTLPG_BILLING_EMAIL = "billing@smartlpg.com";

function utcTo12h(hourUtc, minuteUtc) {
  const h = ((Number(hourUtc) % 24) + 24) % 24;
  const m = Math.min(59, Math.max(0, Number(minuteUtc) || 0));
  const period = h >= 12 ? "PM" : "AM";
  let h12 = h % 12;
  if (h12 === 0) h12 = 12;
  return { hour12: h12, minute: m, period };
}

function twelveToUtc(hour12, minute, period) {
  let h = Number(hour12);
  const m = Math.min(59, Math.max(0, Number(minute) || 0));
  if (period === "AM") {
    if (h === 12) h = 0;
    else h = h % 12;
  } else {
    if (h === 12) h = 12;
    else h = (h % 12) + 12;
  }
  return { send_hour_utc: h, send_minute_utc: m };
}

function formatIso(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function UtilityBillingScheduleSection({ onSave }) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [schedule, setSchedule] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!isSmartLPGTenant(user?.tenant_id)) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await getUtilityBillingScheduleFromFirebase();
        if (!cancelled) {
          setSchedule(data);
        }
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load schedule");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.tenant_id]);

  if (!isSmartLPGTenant(user?.tenant_id)) {
    return null;
  }

  const update = (patch) => {
    setSchedule((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const handleSave = async () => {
    if (!schedule) return;
    setSaving(true);
    setError(null);
    try {
      await saveUtilityBillingScheduleToFirebase(schedule);
      const fresh = await getUtilityBillingScheduleFromFirebase();
      setSchedule(fresh);
      if (onSave) onSave();
    } catch (e) {
      setError(e.message || "Failed to save schedule");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !schedule) {
    return (
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <div className="card__body">
          <p style={{ color: "var(--color-text-secondary)", margin: 0 }}>
            <Icon name="activity" size={18} /> Loading automatic report settings…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ marginBottom: "var(--space-6)" }}>
      <div className="card__header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
        <h3 className="card__title" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", margin: 0 }}>
          <Icon name="send" size={20} /> Automatic report emails
        </h3>
        <label className="badge" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer", padding: "var(--space-2) var(--space-3)", background: schedule.enabled ? "var(--color-success-50, #f0fdf4)" : "var(--color-bg-secondary, #f4f4f5)", color: schedule.enabled ? "var(--color-success-700, #15803d)" : "var(--color-text-secondary)", border: "none" }}>
          <input
            type="checkbox"
            checked={Boolean(schedule.enabled)}
            onChange={(e) => update({ enabled: e.target.checked })}
            style={{ margin: 0, cursor: "pointer", width: "16px", height: "16px" }}
          />
          <span style={{ fontWeight: "500" }}>{schedule.enabled ? "Active" : "Paused"}</span>
        </label>
      </div>
      <div className="card__body">
        <div className="form" style={{ opacity: schedule.enabled ? 1 : 0.7, transition: "opacity 0.2s ease" }}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">
                <Icon name="calendar" size={16} /> Frequency
              </label>
              <select
                className="form-select"
                value={schedule.frequency}
                onChange={(e) => update({ frequency: e.target.value })}
              >
                {FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">
                <Icon name="file" size={16} /> Report type
              </label>
              <select
                className="form-select"
                value={schedule.report_kind}
                onChange={(e) => update({ report_kind: e.target.value })}
              >
                <option value="consolidated">Consolidated (tenant totals)</option>
                <option value="per_device">Per-device</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Send time (UTC)</label>
              <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "center" }}>
                {(() => {
                  const { hour12, minute, period } = utcTo12h(
                    schedule.send_hour_utc,
                    schedule.send_minute_utc
                  );
                  return (
                    <>
                      <select
                        className="form-select"
                        style={{ width: "88px" }}
                        value={hour12}
                        onChange={(e) =>
                          update(
                            twelveToUtc(
                              Number(e.target.value),
                              minute,
                              period
                            )
                          )
                        }
                      >
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                      <span style={{ alignSelf: "center" }}>:</span>
                      <input
                        className="form-input"
                        type="number"
                        min={0}
                        max={59}
                        value={minute}
                        onChange={(e) =>
                          update(
                            twelveToUtc(
                              hour12,
                              Math.min(59, Math.max(0, Number(e.target.value))),
                              period
                            )
                          )
                        }
                        style={{ width: "72px" }}
                        title="Minute"
                      />
                      <select
                        className="form-select"
                        style={{ width: "100px" }}
                        value={period}
                        onChange={(e) =>
                          update(
                            twelveToUtc(hour12, minute, e.target.value)
                          )
                        }
                      >
                        <option value="AM">AM</option>
                        <option value="PM">PM</option>
                      </select>
                    </>
                  );
                })()}
              </div>
              <p
                className="form-help"
                style={{
                  marginTop: "var(--space-2)",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--color-text-tertiary)",
                }}
              >
                Time is stored in UTC (same as the server). Example: 6:00 PM UTC = 18:00.
              </p>
            </div>

            {schedule.frequency === "weekly" && (
              <div className="form-group">
                <label className="form-label">Day of week (UTC)</label>
                <select
                  className="form-select"
                  value={schedule.day_of_week}
                  onChange={(e) => update({ day_of_week: Number(e.target.value) })}
                >
                  {WEEKDAYS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {(schedule.frequency === "monthly" ||
              schedule.frequency === "quarterly" ||
              schedule.frequency === "yearly") && (
              <div className="form-group">
                <label className="form-label">Day of month (1–28)</label>
                <input
                  className="form-input"
                  type="number"
                  min={1}
                  max={28}
                  value={schedule.day_of_month}
                  onChange={(e) => update({ day_of_month: Math.min(28, Math.max(1, Number(e.target.value))) })}
                  style={{ width: "100px" }}
                />
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">
              <Icon name="send" size={16} /> Recipient email
            </label>
            <div
              className="form-input"
              style={{
                background: "var(--color-bg-secondary, #f4f4f5)",
                cursor: "default",
                color: "var(--color-text-primary)",
              }}
            >
              <code style={{ fontSize: "var(--font-size-sm)" }}>{SMARTLPG_BILLING_EMAIL}</code>
            </div>
            <p className="form-help" style={{ fontSize: "var(--font-size-xs)", marginTop: "var(--space-2)" }}>
              Managed on the admin side for this tenant. Reports are always addressed here when saved.
            </p>
          </div>

          <div
            style={{
              display: "flex",
              gap: "var(--space-6)",
              padding: "var(--space-3)",
              background: "var(--color-bg-secondary, #f4f4f5)",
              borderRadius: "var(--border-radius-md)",
              marginBottom: "var(--space-4)",
            }}
          >
            <div>
              <div style={{ color: "var(--color-text-tertiary)", fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "600" }}>Last Sent</div>
              <div style={{ fontWeight: "500", color: "var(--color-text-primary)", marginTop: "4px", fontSize: "var(--font-size-sm)" }}>{formatIso(schedule.last_sent_at)}</div>
            </div>
            <div>
              <div style={{ color: "var(--color-text-tertiary)", fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "600" }}>Next Send</div>
              <div style={{ fontWeight: "500", color: "var(--color-text-primary)", marginTop: "4px", fontSize: "var(--font-size-sm)" }}>{formatIso(schedule.next_send_at)}</div>
            </div>
          </div>

          {error && (
            <div className="badge badge--error" style={{ display: "block", marginBottom: "var(--space-4)" }}>
              {error}
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn--primary" onClick={handleSave} disabled={saving}>
              <Icon name="check" size={18} />
              {saving ? "Saving…" : "Save schedule"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
