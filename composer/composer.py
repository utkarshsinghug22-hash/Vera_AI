"""
composer/composer.py — Main LLM-powered composition engine.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from core.store import store
from core.conversation import conversation_manager
from prompts.system import VERA_SYSTEM_PROMPT, VERA_REPLY_SYSTEM_PROMPT
from prompts.trigger_prompts import build_prompt
from services.llm_client import get_llm_client, parse_json_response
from utils.auto_reply_detector import is_auto_reply, is_identical_to_previous
from utils.intent_detector import detect_intent, get_reject_response, get_off_topic_redirect
import config


def compose_tick(trigger_id: str) -> Optional[dict]:
    """
    Compose a proactive message for a trigger.
    Returns an action dict or None if nothing should be sent.
    """
    trigger, merchant, category, customer = store.get_trigger_context(trigger_id)
    if not trigger or not merchant or not category:
        return None

    suppression_key = trigger.get("suppression_key", trigger_id)
    if conversation_manager.is_suppression_key_fired(suppression_key):
        return None

    merchant_id = trigger.get("merchant_id", "")
    customer_id = trigger.get("customer_id")
    conv_id = f"conv_{merchant_id}_{trigger_id[:20]}"

    # Build user prompt
    user_prompt = build_prompt(category, merchant, trigger, customer)

    # Call LLM
    llm = get_llm_client()
    try:
        raw = llm.complete(VERA_SYSTEM_PROMPT, user_prompt)
        parsed = parse_json_response(raw)
    except Exception as e:
        # Fallback: rule-based
        parsed = _fallback_compose(merchant, trigger, customer)

    body = parsed.get("body", "").strip()
    if not body:
        return None

    body = _clean(body)
    cta = parsed.get("cta", "open_ended")
    rationale = parsed.get("rationale", f"Composed for trigger {trigger.get('kind')}")

    # Template params extraction
    identity = merchant.get("identity", {})
    owner = identity.get("owner_first_name", identity.get("name", ""))
    template_params = [owner, trigger.get("kind", ""), body[:80]]

    send_as = "merchant_on_behalf" if customer else "vera"

    # Record in conversation history
    conversation_manager.get_or_create(conv_id, merchant_id, customer_id, trigger_id)
    conversation_manager.add_turn(conv_id, "vera", body)
    conversation_manager.mark_suppression_fired(suppression_key)

    return {
        "conversation_id": conv_id,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "send_as": send_as,
        "trigger_id": trigger_id,
        "template_name": f"vera_{trigger.get('kind', 'generic')}_v1",
        "template_params": template_params,
        "body": body,
        "cta": cta,
        "suppression_key": suppression_key,
        "rationale": rationale,
    }


def compose_reply(
    conv_id: str,
    merchant_id: str,
    customer_id: Optional[str],
    merchant_message: str,
    turn_number: int,
) -> dict:
    """
    Compose a reply to a merchant/customer message.
    Returns action dict with action=send|wait|end.
    """
    if conversation_manager.is_suppressed(conv_id):
        return {"action": "end", "rationale": "Conversation previously suppressed."}

    # Get conversation history
    history = conversation_manager.get_history(conv_id)
    prev_merchant_msgs = [t.body for t in history if t.role in ("merchant", "customer")]

    # Check auto-reply
    if is_auto_reply(merchant_message) or is_identical_to_previous(merchant_message, prev_merchant_msgs[:-1] if prev_merchant_msgs else []):
        count = conversation_manager.increment_auto_reply(conv_id)
        conversation_manager.add_turn(conv_id, "merchant", merchant_message, is_auto_reply=True, merchant_id=merchant_id)

        if count == 1:
            body = "Looks like an auto-reply 😊 When the owner's free, just reply 'Yes' to continue."
            conversation_manager.add_turn(conv_id, "vera", body)
            return {"action": "send", "body": body, "cta": "binary_yes_no",
                    "rationale": "First auto-reply detected; leaving a note for the owner."}
        elif count == 2:
            return {"action": "wait", "wait_seconds": 14400,
                    "rationale": "Second auto-reply; owner not available. Backing off 4 hours."}
        else:
            conversation_manager.suppress(conv_id)
            return {"action": "end", "rationale": "Three consecutive auto-replies. Ending to avoid noise."}

    # Record merchant message
    conversation_manager.add_turn(conv_id, "merchant", merchant_message, merchant_id=merchant_id)

    # Detect intent
    intent = detect_intent(merchant_message)

    if intent == "reject":
        conversation_manager.suppress(conv_id)
        return get_reject_response()

    if intent == "off_topic":
        body = get_off_topic_redirect()
        conversation_manager.add_turn(conv_id, "vera", body)
        return {"action": "send", "body": body, "cta": "open_ended",
                "rationale": "Off-topic request politely redirected back to business context."}

    # For commit/question/unknown — use LLM with conversation context
    merchant = store.get("merchant", merchant_id) or {}
    category_slug = merchant.get("category_slug", "")
    category = store.get("category", category_slug) or {}

    hist_text = "\n".join(
        f"[{t.role.upper()}]: {t.body}" for t in history[-6:]
    )
    if intent == "commit":
        conversation_manager.set_action_mode(conv_id)

    user_prompt = f"""CONVERSATION HISTORY (last 6 turns):
{hist_text}

MERCHANT LATEST: "{merchant_message}"
DETECTED INTENT: {intent}
{"*** MERCHANT COMMITTED — switch to ACTION MODE immediately. Draft the artifact they agreed to. NO qualifying questions. ***" if intent == "commit" else ""}

MERCHANT: {merchant.get("identity", {}).get("name", "")}
Category: {category_slug}
Language: {merchant.get("identity", {}).get("languages", ["en"])}
Active offer: {next((o["title"] for o in merchant.get("offers", []) if o.get("status") == "active"), "N/A")}

Compose the next Vera reply. Follow all voice/specificity/engagement rules.
Return JSON: {{"action":"send","body":"...","cta":"open_ended|binary_yes_no|none","rationale":"..."}}"""

    llm = get_llm_client()
    try:
        raw = llm.complete(VERA_REPLY_SYSTEM_PROMPT, user_prompt)
        parsed = parse_json_response(raw)
    except Exception:
        parsed = {"action": "send",
                  "body": "Got it — let me work on that now. I'll send you the draft shortly.",
                  "cta": "open_ended",
                  "rationale": "LLM fallback reply."}

    action = parsed.get("action", "send")
    body = _clean(parsed.get("body", ""))

    if action == "send" and body:
        conversation_manager.add_turn(conv_id, "vera", body)

    return {
        "action": action,
        "body": body if action == "send" else None,
        "cta": parsed.get("cta", "open_ended"),
        "wait_seconds": parsed.get("wait_seconds", 3600) if action == "wait" else None,
        "rationale": parsed.get("rationale", ""),
    }


def _clean(text: str) -> str:
    """Remove URLs and clean whitespace."""
    import re
    text = re.sub(r'https?://\S+', '', text)
    return " ".join(text.split()).strip()


def _fallback_compose(merchant: dict, trigger: dict, customer: Optional[dict]) -> dict:
    """Rule-based fallback when LLM fails."""
    identity = merchant.get("identity", {})
    owner = identity.get("owner_first_name", identity.get("name", ""))
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})
    offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
    offer = offers[0]["title"] if offers else "your active offer"

    if customer:
        cname = customer.get("identity", {}).get("name", "there")
        body = f"Hi {cname}, {identity.get('name', '')} here. Just a quick reminder — please get in touch to schedule your next appointment."
        return {"body": body, "cta": "binary_yes_no", "rationale": "Fallback customer recall."}

    body = f"{owner or identity.get('name', '')}, quick update on your profile — your {offer} is active. Want me to draft a Google post around it?"
    return {"body": body, "cta": "binary_yes_no", "rationale": f"Fallback for trigger {kind}."}
