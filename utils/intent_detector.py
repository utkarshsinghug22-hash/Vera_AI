"""
utils/intent_detector.py — Detect merchant intent in replies.

Classifies merchant messages into actionable intent categories:
- commit: merchant agreed / wants to proceed
- reject: merchant opted out / hostile
- question: merchant has a clarifying question
- off_topic: merchant asking about unrelated thing
- auto_reply: WhatsApp Business automated response
- unknown: unclear intent
"""

import re
from typing import Literal

IntentType = Literal["commit", "reject", "question", "off_topic", "auto_reply", "unknown"]


# ── Commit signals ────────────────────────────────────────────────────────────

COMMIT_PHRASES = [
    # English
    "yes", "yes please", "yes do it", "ok", "okay", "sure", "go ahead",
    "let's do it", "lets do it", "let's go", "lets go", "do it", "send it",
    "send", "next", "proceed", "confirm", "confirmed", "agreed", "agree",
    "sounds good", "looks good", "great", "perfect", "awesome",
    "i want", "i'd like", "please do", "please go ahead",
    "draft it", "write it", "make it", "create it", "post it",
    "schedule it", "share it", "publish it",
    # Hindi/Hinglish
    "haan", "ha", "haa", "bilkul", "zaroor", "theek hai", "thik hai",
    "karo", "kar do", "kar dijiye", "chalega", "chalo", "chale",
    "ho jayega", "ho jaye", "accha", "achha", "sahi hai",
    "main chahta", "chahiye", "yes karo",
]

COMMIT_PATTERNS = [
    re.compile(r"\byes\b", re.IGNORECASE),
    re.compile(r"\bok\b", re.IGNORECASE),
    re.compile(r"\bhaan\b", re.IGNORECASE),
    re.compile(r"let.?s do", re.IGNORECASE),
    re.compile(r"go ahead", re.IGNORECASE),
    re.compile(r"do it", re.IGNORECASE),
    re.compile(r"sounds good", re.IGNORECASE),
    re.compile(r"karo\b", re.IGNORECASE),
    re.compile(r"chalega\b", re.IGNORECASE),
    re.compile(r"bilkul\b", re.IGNORECASE),
]

# ── Reject signals ────────────────────────────────────────────────────────────

REJECT_PHRASES = [
    "stop", "stop messaging", "stop messaging me", "don't message",
    "do not message", "not interested", "no thanks", "no thank you",
    "spam", "useless", "waste of time", "please stop",
    "band karo", "rukko", "mat bhejo", "nahi chahiye",
    "mujhe nahi chahiye", "bekar", "faltu",
    "i don't want", "i do not want", "remove me",
    "unsubscribe", "opt out",
]

# ── Question signals ──────────────────────────────────────────────────────────

QUESTION_PATTERNS = [
    re.compile(r"\?"),
    re.compile(r"\bhow\b", re.IGNORECASE),
    re.compile(r"\bwhat\b", re.IGNORECASE),
    re.compile(r"\bwhen\b", re.IGNORECASE),
    re.compile(r"\bwhere\b", re.IGNORECASE),
    re.compile(r"\bwhy\b", re.IGNORECASE),
    re.compile(r"\bkya\b", re.IGNORECASE),
    re.compile(r"\bkaise\b", re.IGNORECASE),
    re.compile(r"\bkab\b", re.IGNORECASE),
    re.compile(r"\bkitna\b", re.IGNORECASE),
    re.compile(r"\bkahan\b", re.IGNORECASE),
    re.compile(r"can you", re.IGNORECASE),
    re.compile(r"could you", re.IGNORECASE),
    re.compile(r"would you", re.IGNORECASE),
    re.compile(r"tell me", re.IGNORECASE),
]

# ── Off-topic signals ─────────────────────────────────────────────────────────

OFF_TOPIC_PHRASES = [
    "gst", "income tax", "tax filing", "itr",
    "loan", "insurance", "credit card",
    "hire", "job opening", "recruitment",
    "delivery address", "shipping",
    "refund", "complaint",
]


def detect_intent(message: str) -> IntentType:
    """
    Classify merchant message intent.
    
    Priority order:
    1. Auto-reply check (delegate to auto_reply_detector)
    2. Reject signals
    3. Commit signals (explicit positive action)
    4. Off-topic check
    5. Question check
    6. Unknown
    """
    from utils.auto_reply_detector import is_auto_reply

    if not message:
        return "unknown"

    msg_lower = message.lower().strip()

    # 1. Auto-reply check
    if is_auto_reply(message):
        return "auto_reply"

    # 2. Reject signals
    for phrase in REJECT_PHRASES:
        if phrase in msg_lower:
            return "reject"

    # 3. Commit signals — word-boundary matching
    for phrase in COMMIT_PHRASES:
        # Check with word boundary awareness for short words
        if len(phrase) <= 3:
            # Use regex for short words to avoid false positives
            pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
            if pattern.search(msg_lower):
                return "commit"
        elif phrase in msg_lower:
            return "commit"

    for pattern in COMMIT_PATTERNS:
        if pattern.search(msg_lower):
            return "commit"

    # 4. Off-topic signals
    for phrase in OFF_TOPIC_PHRASES:
        if phrase in msg_lower:
            return "off_topic"

    # 5. Question signals
    for pattern in QUESTION_PATTERNS:
        if pattern.search(message):  # use original for ? detection
            return "question"

    return "unknown"


def get_reject_response() -> dict:
    """Return the standard graceful exit response."""
    return {
        "action": "end",
        "rationale": "Merchant opted out or expressed disinterest. Closing conversation gracefully without further follow-up.",
    }


def get_off_topic_redirect(topic_detected: str = "that") -> str:
    """Return a polite redirect for off-topic requests."""
    responses = [
        f"That's outside what I can help with directly — for {topic_detected}, you'd want to connect with a specialist. Coming back to your business — what would be most useful right now?",
        f"I'll have to leave {topic_detected} to the relevant experts. Want me to focus on what I can do — your Google profile, offers, or customer messaging?",
        f"That's beyond my scope, but happy to help with your magicpin presence. What should I focus on?",
    ]
    return responses[0]
