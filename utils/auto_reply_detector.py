"""
utils/auto_reply_detector.py — Detect WhatsApp Business auto-replies.

Uses multi-signal approach:
1. Known phrase matching (common canned responses)
2. Structural patterns (formulaic acknowledgment structure)
3. Absence of intent markers (no question, no personal address)
"""

import re
from typing import Optional


# ── Known auto-reply phrases ─────────────────────────────────────────────────
# Collected from challenge case studies + common WA Business patterns

AUTO_REPLY_PHRASES = [
    "thank you for contacting",
    "thanks for contacting",
    "thanks for reaching out",
    "thank you for reaching out",
    "we will respond shortly",
    "we'll respond shortly",
    "our team will respond",
    "our representative will get back",
    "someone from our team will",
    "we have received your message",
    "your message has been received",
    "automated response",
    "auto reply",
    "this is an automated message",
    "i am an automated assistant",
    "main ek automated assistant hoon",
    "yeh ek automated message hai",
    "main aapki baat hamari team tak pahuncha",
    "hamari team tak pahuncha deti hoon",
    "team tak pahunchane se pehle",
    "business hours mein jawab milega",
    "we are currently unavailable",
    "currently not available",
    "out of office",
    "oop! i am on vacation",
]

# ── Regex patterns for structural detection ───────────────────────────────────

# Formulaic acknowledgment: "[Thank you / Shukriya / Dhanyawad] ... [team / representative / contact]"
_FORMULAIC_PATTERN = re.compile(
    r"(thank|shukriya|dhanyawad|aapki madad|namaskar|bahut bahut).*"
    r"(team|representative|staff|sampark|contact|pahunch)",
    re.IGNORECASE,
)

# Long mechanical response (>100 chars) with no question mark
_LONG_NO_QUESTION = re.compile(r"^[^?]{120,}$")


def is_auto_reply(message: str) -> bool:
    """
    Detect if a merchant message is a WhatsApp Business auto-reply.
    
    Returns True if the message appears to be canned/automated.
    """
    if not message:
        return False

    msg_lower = message.lower().strip()

    # 1. Direct phrase match
    for phrase in AUTO_REPLY_PHRASES:
        if phrase in msg_lower:
            return True

    # 2. Structural formula match
    if _FORMULAIC_PATTERN.search(msg_lower):
        return True

    # 3. Long message with no question and no personal engagement markers
    if _LONG_NO_QUESTION.match(msg_lower):
        engagement_markers = ["i ", "we ", "my ", "our ", "yes", "no ", "ok", "karo", "chahiye", "?"]
        has_engagement = any(m in msg_lower for m in engagement_markers)
        if not has_engagement:
            return True

    return False


def is_identical_to_previous(message: str, previous_messages: list[str]) -> bool:
    """
    Check if a message is identical or near-identical to any previous message in the conversation.
    Used for auto-reply escalation (same text 2+ times = definitely auto-reply).
    """
    msg_clean = message.strip().lower()
    for prev in previous_messages:
        if prev.strip().lower() == msg_clean:
            return True
    return False
