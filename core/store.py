"""
core/store.py — Thread-safe, versioned context store.

Handles all 4 context scopes: category, merchant, customer, trigger.
Implements idempotency contract: same version = 409, higher version = atomic replace.
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class ContextStore:
    """
    In-memory context store with version management.
    
    All 4 context scopes are stored as flat dicts keyed by context_id.
    Version tracking ensures idempotent pushes and atomic replacements.
    """

    VALID_SCOPES = {"category", "merchant", "customer", "trigger"}

    def __init__(self):
        self._lock = threading.Lock()
        # {scope: {context_id: payload}}
        self._data: Dict[str, Dict[str, Any]] = {
            "category": {},
            "merchant": {},
            "customer": {},
            "trigger": {},
        }
        # {context_id: version}
        self._versions: Dict[str, int] = {}

    def push(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Push a context update.
        
        Returns:
            (accepted, reason, current_version)
            - accepted=True: stored successfully
            - accepted=False + reason="stale_version": we have a higher or equal version
            - accepted=False + reason="invalid_scope": unknown scope
        """
        if scope not in self.VALID_SCOPES:
            return False, "invalid_scope", None

        with self._lock:
            current_ver = self._versions.get(context_id, 0)
            if version <= current_ver:
                return False, "stale_version", current_ver

            self._data[scope][context_id] = payload
            self._versions[context_id] = version
            return True, None, None

    def get(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        """Get a context payload by scope and id."""
        with self._lock:
            return self._data.get(scope, {}).get(context_id)

    def get_all(self, scope: str) -> Dict[str, Any]:
        """Get all payloads for a given scope."""
        with self._lock:
            return dict(self._data.get(scope, {}))

    def count(self, scope: str) -> int:
        """Count stored contexts for a scope."""
        with self._lock:
            return len(self._data.get(scope, {}))

    def counts(self) -> Dict[str, int]:
        """Return count of all stored contexts per scope."""
        with self._lock:
            return {scope: len(data) for scope, data in self._data.items()}

    def get_merchant_with_category(
        self, merchant_id: str
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Convenience method: fetch merchant + its category in one call.
        Returns (merchant_payload, category_payload). Either can be None.
        """
        merchant = self.get("merchant", merchant_id)
        if not merchant:
            return None, None
        category_slug = merchant.get("category_slug")
        category = self.get("category", category_slug) if category_slug else None
        return merchant, category

    def get_trigger_context(
        self, trigger_id: str
    ) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict]]:
        """
        Convenience method: given a trigger_id, return full 4-context tuple.
        Returns (trigger, merchant, category, customer). Any can be None.
        """
        trigger = self.get("trigger", trigger_id)
        if not trigger:
            return None, None, None, None

        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")

        merchant, category = self.get_merchant_with_category(merchant_id) if merchant_id else (None, None)
        customer = self.get("customer", customer_id) if customer_id else None

        return trigger, merchant, category, customer

    def teardown(self):
        """Wipe all state (called on /v1/teardown)."""
        with self._lock:
            for scope in self._data:
                self._data[scope].clear()
            self._versions.clear()


# Global singleton
store = ContextStore()
