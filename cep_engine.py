"""Complex Event Processing (CEP) engine for detecting patterns across multiple events."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Deque
from collections import deque, defaultdict

from database import SessionLocal
from models import Device, CEPRule, TelemetryTimeseries
from rule_engine import rule_engine

logger = logging.getLogger(__name__)


class CEPEngine:
    """Engine for detecting complex event patterns across multiple devices/events."""
    
    def __init__(self):
        """Initialize CEP engine."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._event_buffer: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=1000))
        self._lock = threading.Lock()
    
    def start(self):
        """Start the CEP engine worker."""
        if self._running:
            logger.warning("CEP engine is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("CEP engine started")
    
    def stop(self):
        """Stop the CEP engine."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("CEP engine stopped")
    
    def process_event(self, device_id: str, payload: Dict[str, Any], metadata: Dict[str, Any]):
        """Process an incoming event for CEP pattern matching."""
        with self._lock:
            event = {
                "device_id": device_id,
                "payload": payload,
                "metadata": metadata,
                "timestamp": datetime.now(timezone.utc)
            }
            # Store event in buffer (keyed by tenant or device pattern)
            tenant_id = metadata.get("tenant_id")
            if tenant_id:
                self._event_buffer[f"tenant_{tenant_id}"].append(event)
            self._event_buffer[device_id].append(event)
    
    def _worker_loop(self):
        """Background worker that processes CEP rules."""
        while self._running:
            try:
                self._process_cep_rules()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in CEP engine worker loop: {e}", exc_info=True)
                time.sleep(30)
    
    def _process_cep_rules(self):
        """Process all active CEP rules."""
        db = SessionLocal()
        try:
            cep_rules = db.query(CEPRule).filter(
                CEPRule.is_active == True
            ).all()
            
            for rule in cep_rules:
                try:
                    self._evaluate_cep_rule(rule, db)
                except Exception as e:
                    logger.error(f"Error evaluating CEP rule {rule.id}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error in _process_cep_rules: {e}", exc_info=True)
        finally:
            db.close()
    
    def _evaluate_cep_rule(self, rule: CEPRule, db: SessionLocal):
        """Evaluate a CEP rule against recent events."""
        pattern = rule.pattern
        pattern_type = pattern.get("type", "sequence")  # sequence, window, aggregate
        
        # Get events from buffer for this tenant
        tenant_key = f"tenant_{rule.tenant_id}"
        with self._lock:
            events = list(self._event_buffer.get(tenant_key, []))
        
        if len(events) < rule.min_events:
            return
        
        # Filter events within time window
        window_start = datetime.now(timezone.utc) - timedelta(seconds=rule.window_seconds)
        recent_events = [e for e in events if e["timestamp"] >= window_start]
        
        if len(recent_events) < rule.min_events:
            return
        
        # Evaluate pattern based on type
        matched = False
        
        if pattern_type == "sequence":
            matched = self._match_sequence_pattern(pattern, recent_events)
        elif pattern_type == "window":
            matched = self._match_window_pattern(pattern, recent_events)
        elif pattern_type == "aggregate":
            matched = self._match_aggregate_pattern(pattern, recent_events)
        
        if matched:
            # Check condition on matched pattern
            condition_met = self._evaluate_condition(rule.condition, recent_events)
            
            if condition_met:
                # Execute action
                self._execute_action(rule.action, recent_events, rule.tenant_id, db)
                
                # Update rule stats
                rule.last_matched_at = datetime.now(timezone.utc)
                rule.match_count += 1
                db.commit()
                
                logger.info(f"CEP rule '{rule.name}' matched pattern and executed action")
    
    def _match_sequence_pattern(self, pattern: Dict[str, Any], events: List[Dict[str, Any]]) -> bool:
        """Match a sequence pattern (events in specific order)."""
        sequence = pattern.get("sequence", [])
        if not sequence:
            return False
        
        # Simple sequence matching: check if events match sequence in order
        event_idx = 0
        for step in sequence:
            device_id = step.get("device_id")
            condition = step.get("condition", {})
            
            # Find matching event
            found = False
            while event_idx < len(events):
                event = events[event_idx]
                if device_id and event["device_id"] != device_id:
                    event_idx += 1
                    continue
                
                # Check condition
                if self._check_event_condition(event, condition):
                    found = True
                    event_idx += 1
                    break
                event_idx += 1
            
            if not found:
                return False
        
        return True
    
    def _match_window_pattern(self, pattern: Dict[str, Any], events: List[Dict[str, Any]]) -> bool:
        """Match a window pattern (events within time window)."""
        conditions = pattern.get("conditions", [])
        if not conditions:
            return False
        
        # Check if all conditions are met by events in window
        for condition in conditions:
            device_id = condition.get("device_id")
            field_condition = condition.get("condition", {})
            
            # Find matching event
            found = False
            for event in events:
                if device_id and event["device_id"] != device_id:
                    continue
                if self._check_event_condition(event, field_condition):
                    found = True
                    break
            
            if not found:
                return False
        
        return True
    
    def _match_aggregate_pattern(self, pattern: Dict[str, Any], events: List[Dict[str, Any]]) -> bool:
        """Match an aggregate pattern (count, sum, avg, etc.)."""
        aggregation = pattern.get("aggregation", {})
        agg_type = aggregation.get("type")  # count, sum, avg, min, max
        field = aggregation.get("field")
        threshold = aggregation.get("threshold")
        
        if not agg_type or not field:
            return False
        
        values = []
        for event in events:
            value = self._extract_field(event["payload"], field)
            if value is not None:
                values.append(value)
        
        if not values:
            return False
        
        # Calculate aggregate
        if agg_type == "count":
            result = len(values)
        elif agg_type == "sum":
            result = sum(v for v in values if isinstance(v, (int, float)))
        elif agg_type == "avg":
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            result = sum(numeric_values) / len(numeric_values) if numeric_values else 0
        elif agg_type == "min":
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            result = min(numeric_values) if numeric_values else None
        elif agg_type == "max":
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            result = max(numeric_values) if numeric_values else None
        else:
            return False
        
        # Compare with threshold
        if threshold is not None:
            op = aggregation.get("operator", ">=")
            if op == ">=":
                return result >= threshold
            elif op == "<=":
                return result <= threshold
            elif op == ">":
                return result > threshold
            elif op == "<":
                return result < threshold
            elif op == "==":
                return result == threshold
        
        return True
    
    def _check_event_condition(self, event: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """Check if an event matches a condition."""
        field = condition.get("field")
        op = condition.get("op", "==")
        value = condition.get("value")
        
        field_value = self._extract_field(event["payload"], field)
        
        if op == "==":
            return field_value == value
        elif op == "!=":
            return field_value != value
        elif op == ">":
            return isinstance(field_value, (int, float)) and field_value > value
        elif op == "<":
            return isinstance(field_value, (int, float)) and field_value < value
        elif op == ">=":
            return isinstance(field_value, (int, float)) and field_value >= value
        elif op == "<=":
            return isinstance(field_value, (int, float)) and field_value <= value
        
        return False
    
    def _evaluate_condition(self, condition: Dict[str, Any], events: List[Dict[str, Any]]) -> bool:
        """Evaluate condition on matched pattern events."""
        # Use rule engine's condition evaluation
        # Create a synthetic context from matched events
        context = {
            "events": events,
            "event_count": len(events),
            "first_event": events[0] if events else None,
            "last_event": events[-1] if events else None,
        }
        
        return rule_engine._evaluate_condition(condition, context)
    
    def _execute_action(self, action: Dict[str, Any], events: List[Dict[str, Any]], tenant_id: int, db: SessionLocal):
        """Execute action for matched CEP pattern."""
        context = {
            "payload": {},
            "metadata": {
                "source": "cep_rule",
                "tenant_id": tenant_id,
                "matched_events": len(events)
            },
            "device": {
                "tenant_id": tenant_id
            },
            "events": events
        }
        
        rule_engine._apply_action(action, {}, {}, context=context)
    
    @staticmethod
    def _extract_field(data: Dict[str, Any], path: Optional[str]) -> Any:
        """Extract field value from nested dict using dot notation."""
        if not path:
            return None
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value


# Global CEP engine instance
cep_engine = CEPEngine()

