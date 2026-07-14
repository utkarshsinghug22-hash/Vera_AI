"""
core/conversation.py — Multi-turn conversation state manager.

Tracks:
- Full turn history per conversation_id
- Auto-reply counter per conversation (for detection + escalation)
- Intent state per conversation (qualifying vs. action mode)
- Global suppression key registry (prevents re-firing same trigger)
- Opted-out conversations (hard "not interested" signals)
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set


@dataclass
class Turn:
    role: str          # "vera" | "merchant" | "customer"
    body: str
    timestamp: str
    is_auto_reply: bool = False


@dataclass
class Conversation:
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    turns: List[Turn] = field(default_factory=list)
    auto_reply_count: int = 0
    is_suppressed: bool = False   # merchant said "not interested"
    in_action_mode: bool = False  # merchant committed → no more qualifying
    trigger_id: Optional[str] = None


class ConversationManager:
    """
    Manages all active conversation states.
    
    Key behaviours:
    - add_turn(): append a turn to a conversation
    - increment_auto_reply(): track consecutive auto-replies
    - suppress(): mark a conversation as opted-out
    - get_auto_reply_count(): used to escalate: 1=try once, 2=wait, 3+=end
    - Global suppression: track fired suppression_keys across all conversations
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._conversations: Dict[str, Conversation] = {}
        # Global set of fired suppression keys (prevent re-send)
        self._fired_suppressions: Set[str] = set()

    # ── Conversation lifecycle ────────────────────────────────────────────────

    def get_or_create(
        self,
        conv_id: str,
        merchant_id: str,
        customer_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
    ) -> Conversation:
        with self._lock:
            if conv_id not in self._conversations:
                self._conversations[conv_id] = Conversation(
                    conversation_id=conv_id,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    trigger_id=trigger_id,
                )
            return self._conversations[conv_id]

    def get(self, conv_id: str) -> Optional[Conversation]:
        with self._lock:
            return self._conversations.get(conv_id)

    # ── Turn management ───────────────────────────────────────────────────────

    def add_turn(
        self,
        conv_id: str,
        role: str,
        body: str,
        is_auto_reply: bool = False,
        merchant_id: str = "",
    ) -> None:
        with self._lock:
            if conv_id not in self._conversations:
                self._conversations[conv_id] = Conversation(
                    conversation_id=conv_id,
                    merchant_id=merchant_id,
                )
            conv = self._conversations[conv_id]
            conv.turns.append(Turn(
                role=role,
                body=body,
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_auto_reply=is_auto_reply,
            ))

    def get_history(self, conv_id: str) -> List[Turn]:
        with self._lock:
            conv = self._conversations.get(conv_id)
            return list(conv.turns) if conv else []

    def get_last_vera_message(self, conv_id: str) -> Optional[str]:
        """Return the last message Vera sent in this conversation."""
        with self._lock:
            conv = self._conversations.get(conv_id)
            if not conv:
                return None
            for turn in reversed(conv.turns):
                if turn.role == "vera":
                    return turn.body
            return None

    def has_vera_sent_recently(self, conv_id: str) -> bool:
        """Check if Vera already sent in this conversation."""
        return self.get_last_vera_message(conv_id) is not None

    # ── Auto-reply tracking ───────────────────────────────────────────────────

    def increment_auto_reply(self, conv_id: str) -> int:
        """Increment auto-reply counter and return new count."""
        with self._lock:
            if conv_id not in self._conversations:
                self._conversations[conv_id] = Conversation(
                    conversation_id=conv_id,
                    merchant_id="",
                )
            self._conversations[conv_id].auto_reply_count += 1
            return self._conversations[conv_id].auto_reply_count

    def get_auto_reply_count(self, conv_id: str) -> int:
        with self._lock:
            conv = self._conversations.get(conv_id)
            return conv.auto_reply_count if conv else 0

    # ── Intent / opt-out state ────────────────────────────────────────────────

    def suppress(self, conv_id: str) -> None:
        """Mark conversation as suppressed (merchant opted out)."""
        with self._lock:
            if conv_id in self._conversations:
                self._conversations[conv_id].is_suppressed = True

    def is_suppressed(self, conv_id: str) -> bool:
        with self._lock:
            conv = self._conversations.get(conv_id)
            return conv.is_suppressed if conv else False

    def set_action_mode(self, conv_id: str) -> None:
        """Merchant committed — switch to action mode (no more qualifying)."""
        with self._lock:
            if conv_id in self._conversations:
                self._conversations[conv_id].in_action_mode = True

    def is_action_mode(self, conv_id: str) -> bool:
        with self._lock:
            conv = self._conversations.get(conv_id)
            return conv.in_action_mode if conv else False

    # ── Global suppression keys ───────────────────────────────────────────────

    def is_suppression_key_fired(self, key: str) -> bool:
        """Check if a suppression key has already been used this session."""
        with self._lock:
            return key in self._fired_suppressions

    def mark_suppression_fired(self, key: str) -> None:
        """Record that a suppression key was fired."""
        with self._lock:
            self._fired_suppressions.add(key)

    def teardown(self):
        """Wipe all conversation state."""
        with self._lock:
            self._conversations.clear()
            self._fired_suppressions.clear()


# Global singleton
conversation_manager = ConversationManager()
