"""Per-device rule engine for inline telemetry decisions with stateful tracking."""
from __future__ import annotations

import copy
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Deque

from database import SessionLocal
from metrics import metrics
from models import Device, DeviceRule

logger = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """Stateful information tracked per device for rule evaluation."""
    device_id: str
    last_values: Dict[str, Any] = field(default_factory=dict)  # field -> value
    value_history: Dict[str, Deque[tuple[float, Any]]] = field(default_factory=dict)  # field -> [(timestamp, value), ...]
    counters: Dict[str, int] = field(default_factory=dict)  # rule-specific counters
    flags: Dict[str, bool] = field(default_factory=dict)  # rule-specific boolean flags
    last_update: float = field(default_factory=time.time)
    
    def get_last_value(self, field: str) -> Optional[Any]:
        """Get the last recorded value for a field."""
        return self.last_values.get(field)
    
    def set_value(self, field: str, value: Any):
        """Record the current value for a field."""
        self.last_values[field] = value
        self.last_update = time.time()
    
    def add_to_history(self, field: str, value: Any, max_history: int = 100, max_age_seconds: int = 3600):
        """Add a value to the time-series history for a field."""
        if field not in self.value_history:
            self.value_history[field] = deque(maxlen=max_history)
        
        now = time.time()
        self.value_history[field].append((now, value))
        
        # Clean old entries
        cutoff = now - max_age_seconds
        while self.value_history[field] and self.value_history[field][0][0] < cutoff:
            self.value_history[field].popleft()
    
    def get_history(self, field: str, seconds: int = 60) -> List[tuple[float, Any]]:
        """Get recent history for a field within the time window."""
        if field not in self.value_history:
            return []
        
        cutoff = time.time() - seconds
        return [(ts, val) for ts, val in self.value_history[field] if ts >= cutoff]
    
    def increment_counter(self, counter_name: str) -> int:
        """Increment a counter and return new value."""
        self.counters[counter_name] = self.counters.get(counter_name, 0) + 1
        return self.counters[counter_name]
    
    def reset_counter(self, counter_name: str):
        """Reset a counter to zero."""
        self.counters[counter_name] = 0
    
    def get_counter(self, counter_name: str) -> int:
        """Get current counter value."""
        return self.counters.get(counter_name, 0)
    
    def set_flag(self, flag_name: str, value: bool):
        """Set a boolean flag."""
        self.flags[flag_name] = value
    
    def get_flag(self, flag_name: str) -> bool:
        """Get a boolean flag."""
        return self.flags.get(flag_name, False)


@dataclass
class RuleEvaluationResult:
    payload: Dict[str, Any]
    metadata: Dict[str, Any]
    target_topic: Optional[str] = None
    dropped: bool = False
    drop_reason: Optional[str] = None
    rule_name: Optional[str] = None
    action_type: Optional[str] = None


class RuleEngine:
    """Stateful rule engine that evaluates per-device rules inline with historical context."""

    def __init__(self, cache_ttl_seconds: int = 30):
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}  # Rule cache
        self._state: Dict[str, DeviceState] = {}  # Device state store
        self._lock = threading.Lock()

    # Public API -----------------------------------------------------------------
    def evaluate(
        self,
        device_id: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
        source: str,
        *,
        device: Optional[Device] = None,
        db_session=None,
    ) -> RuleEvaluationResult:
        """Evaluate device rules and return potentially mutated telemetry."""

        rules = self._get_rules(device_id, db_session)
        if not rules:
            # Still update state even if no rules
            self._update_device_state(device_id, payload)
            return RuleEvaluationResult(payload=payload, metadata=metadata)

        # Get or create device state
        device_state = self._get_device_state(device_id)

        working_payload = copy.deepcopy(payload)
        working_metadata = copy.deepcopy(metadata)
        context = {
            "payload": working_payload,
            "metadata": working_metadata,
            "source": source,
            "device": {
                "device_id": device.device_id if device else device_id,
                "tenant_id": getattr(device, "tenant_id", None),
                "device_type": getattr(device.device_type, "name", None) if device else None,
            },
            "state": device_state,  # Add stateful context
        }

        target_topic = None
        last_rule_name = None
        last_action_type = None

        for rule in rules:
            if not rule["is_active"]:
                continue

            try:
                matched = self._evaluate_condition(rule["condition"], context)
            except Exception as exc:  # Defensive: never block ingestion
                logger.warning("Rule condition error (device=%s rule=%s): %s", device_id, rule["id"], exc)
                continue

            if not matched:
                continue

            action = rule["action"]
            last_rule_name = rule["name"]
            last_action_type = action.get("type", "unknown")

            try:
                decision = self._apply_action(
                    action,
                    working_payload,
                    working_metadata,
                    context=context,
                )
            except Exception as exc:
                logger.warning("Rule action error (device=%s rule=%s): %s", device_id, rule["id"], exc)
                continue

            metrics.record_rule_decision(
                device_id=device_id,
                rule_name=last_rule_name,
                action_type=last_action_type,
                outcome="dropped" if decision.dropped else ("routed" if decision.target_topic else "mutated"),
            )

            if decision.payload is not working_payload:
                working_payload = decision.payload
            if decision.metadata is not working_metadata:
                working_metadata = decision.metadata
            if decision.target_topic:
                target_topic = decision.target_topic

            if decision.dropped or action.get("stop", True):
                decision.rule_name = last_rule_name
                decision.action_type = last_action_type
                # Update state before returning
                self._update_device_state(device_id, working_payload)
                return decision

        # Update device state after successful evaluation
        self._update_device_state(device_id, working_payload)

        return RuleEvaluationResult(
            payload=working_payload,
            metadata=working_metadata,
            target_topic=target_topic,
            rule_name=last_rule_name,
            action_type=last_action_type,
        )

    def invalidate(self, device_id: str):
        """Invalidate cache for a device when rules change."""
        with self._lock:
            if device_id in self._cache:
                del self._cache[device_id]
    
    def clear_state(self, device_id: str):
        """Clear state for a device (useful for testing or reset)."""
        with self._lock:
            if device_id in self._state:
                del self._state[device_id]
    
    def _get_device_state(self, device_id: str) -> DeviceState:
        """Get or create device state."""
        with self._lock:
            if device_id not in self._state:
                self._state[device_id] = DeviceState(device_id=device_id)
            return self._state[device_id]
    
    def _update_device_state(self, device_id: str, payload: Dict[str, Any]):
        """Update device state with current payload values."""
        state = self._get_device_state(device_id)
        
        # Update last values and history for all numeric fields
        for key, value in payload.items():
            state.set_value(key, value)
            if isinstance(value, (int, float)):
                state.add_to_history(key, value)

    # Internal helpers -----------------------------------------------------------
    def _get_rules(self, device_id: str, db_session=None) -> List[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            cached = self._cache.get(device_id)
            if cached and cached["expires_at"] > now:
                return cached["rules"]

        session = db_session or SessionLocal()
        try:
            rules = (
                session.query(DeviceRule)
                .join(Device, Device.id == DeviceRule.device_id)
                .filter(Device.device_id == device_id)
                .order_by(DeviceRule.priority.asc(), DeviceRule.id.asc())
                .all()
            )
            serialized = [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "priority": rule.priority,
                    "is_active": rule.is_active,
                    "condition": rule.condition or {},
                    "action": rule.action or {},
                }
                for rule in rules
            ]
            with self._lock:
                self._cache[device_id] = {"rules": serialized, "expires_at": now + self.cache_ttl}
            return serialized
        finally:
            if db_session is None:
                session.close()

    # Condition evaluation -------------------------------------------------------
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        if not condition:
            return True

        if "all" in condition:
            return all(self._evaluate_condition(clause, context) for clause in condition["all"])
        if "any" in condition:
            return any(self._evaluate_condition(clause, context) for clause in condition["any"])
        if "none" in condition:
            return not any(self._evaluate_condition(clause, context) for clause in condition["none"])

        field_path = condition.get("field")
        op = condition.get("op", "==").lower()
        value = condition.get("value")

        left = self._extract_field(context, field_path)
        if op == "exists":
            return left is not None
        if op == "not_exists":
            return left is None
        if op in {"==", "eq"}:
            return left == value
        if op in {"!=", "ne"}:
            return left != value
        if op in {">", "gt"}:
            return self._safe_compare(left, value, lambda a, b: a > b)
        if op in {"<", "lt"}:
            return self._safe_compare(left, value, lambda a, b: a < b)
        if op in {">=", "gte"}:
            return self._safe_compare(left, value, lambda a, b: a >= b)
        if op in {"<=", "lte"}:
            return self._safe_compare(left, value, lambda a, b: a <= b)
        if op in {"in"}:
            return left in value if isinstance(value, (list, tuple, set)) else False
        if op in {"not_in"}:
            return left not in value if isinstance(value, (list, tuple, set)) else True
        if op == "contains":
            if isinstance(left, (list, tuple, set)):
                return value in left
            if isinstance(left, str):
                return str(value) in left
        if op == "starts_with" and isinstance(left, str):
            return left.startswith(str(value))
        if op == "ends_with" and isinstance(left, str):
            return left.endswith(str(value))
        
        # Stateful operators (require state context)
        state = context.get("state")
        if not state:
            logger.debug("Stateful operator '%s' used but no state available", op)
            return False
        
        if op == "changed":
            # Check if field value changed from last message
            last = state.get_last_value(field_path)
            return last is not None and last != left
        
        if op == "increased_by":
            # Check if field increased by at least the specified amount
            last = state.get_last_value(field_path)
            if last is None or not isinstance(left, (int, float)) or not isinstance(last, (int, float)):
                return False
            return (left - last) >= value
        
        if op == "decreased_by":
            # Check if field decreased by at least the specified amount
            last = state.get_last_value(field_path)
            if last is None or not isinstance(left, (int, float)) or not isinstance(last, (int, float)):
                return False
            return (last - left) >= value
        
        if op == "consecutive_above":
            # Check if field has been above threshold for N consecutive readings
            history = state.get_history(field_path, seconds=value.get("seconds", 300))
            threshold = value.get("threshold")
            count = value.get("count", 3)
            if len(history) < count:
                return False
            recent = [val for _, val in history[-count:]]
            return all(isinstance(v, (int, float)) and v > threshold for v in recent)
        
        if op == "consecutive_below":
            # Check if field has been below threshold for N consecutive readings
            history = state.get_history(field_path, seconds=value.get("seconds", 300))
            threshold = value.get("threshold")
            count = value.get("count", 3)
            if len(history) < count:
                return False
            recent = [val for _, val in history[-count:]]
            return all(isinstance(v, (int, float)) and v < threshold for v in recent)
        
        if op == "rate_of_change":
            # Check if rate of change exceeds threshold over time window
            window_seconds = value.get("seconds", 60)
            threshold = value.get("threshold", 0)
            history = state.get_history(field_path, seconds=window_seconds)
            if len(history) < 2:
                return False
            first_ts, first_val = history[0]
            last_ts, last_val = history[-1]
            if not isinstance(first_val, (int, float)) or not isinstance(last_val, (int, float)):
                return False
            time_delta = last_ts - first_ts
            if time_delta == 0:
                return False
            rate = (last_val - first_val) / time_delta
            return abs(rate) > threshold

        logger.debug("Unsupported operator '%s' in rule condition", op)
        return False

    @staticmethod
    def _extract_field(context: Dict[str, Any], path: Optional[str]) -> Any:
        if not path:
            return None
        parts = path.split(".")
        value: Any = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    @staticmethod
    def _safe_compare(left: Any, right: Any, comparator) -> bool:
        try:
            return comparator(left, right)
        except Exception:
            return False

    # Action execution -----------------------------------------------------------
    def _apply_action(
        self,
        action: Dict[str, Any],
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
        *,
        context: Dict[str, Any],
    ) -> RuleEvaluationResult:
        action_type = action.get("type")
        if action_type == "drop":
            return RuleEvaluationResult(
                payload=payload,
                metadata=metadata,
                dropped=True,
                drop_reason=action.get("reason", "Dropped by rule engine"),
                action_type="drop",
            )

        if action_type == "route":
            return RuleEvaluationResult(
                payload=payload,
                metadata=metadata,
                target_topic=action.get("topic"),
                action_type="route",
            )

        if action_type == "mutate":
            updated_payload = copy.deepcopy(payload)
            updated_metadata = copy.deepcopy(metadata)

            sets = action.get("set", {})
            for path, value in sets.items():
                if path.startswith("metadata."):
                    self._assign_path(updated_metadata, path.replace("metadata.", "", 1), value)
                elif path.startswith("payload."):
                    self._assign_path(updated_payload, path.replace("payload.", "", 1), value)
                else:
                    self._assign_path(updated_metadata, path, value)

            return RuleEvaluationResult(
                payload=updated_payload,
                metadata=updated_metadata,
                action_type="mutate",
            )
        
        # Stateful actions
        state = context.get("state")
        if action_type == "increment_counter" and state:
            counter_name = action.get("counter", "default")
            new_value = state.increment_counter(counter_name)
            logger.debug("Incremented counter '%s' to %d for device %s", counter_name, new_value, state.device_id)
            return RuleEvaluationResult(payload=payload, metadata=metadata, action_type="increment_counter")
        
        if action_type == "reset_counter" and state:
            counter_name = action.get("counter", "default")
            state.reset_counter(counter_name)
            logger.debug("Reset counter '%s' for device %s", counter_name, state.device_id)
            return RuleEvaluationResult(payload=payload, metadata=metadata, action_type="reset_counter")
        
        if action_type == "set_flag" and state:
            flag_name = action.get("flag", "default")
            flag_value = action.get("value", True)
            state.set_flag(flag_name, flag_value)
            logger.debug("Set flag '%s' to %s for device %s", flag_name, flag_value, state.device_id)
            return RuleEvaluationResult(payload=payload, metadata=metadata, action_type="set_flag")

        logger.debug("Unknown action type '%s'; skipping.", action_type)
        return RuleEvaluationResult(payload=payload, metadata=metadata)

    @staticmethod
    def _assign_path(target: Dict[str, Any], path: str, value: Any):
        parts = path.split(".")
        cursor = target
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value


# Global singleton
rule_engine = RuleEngine()


