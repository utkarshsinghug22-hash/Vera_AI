"""
main.py — Vera Bot FastAPI application.

Implements all 5 required endpoints:
  GET  /v1/healthz
  GET  /v1/metadata
  POST /v1/context
  POST /v1/tick
  POST /v1/reply
  POST /v1/teardown  (optional, for cleanup)
"""

import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

import config
from core.store import store
from core.conversation import conversation_manager
from composer.composer import compose_tick, compose_reply

app = FastAPI(title="Vera Bot", version=config.BOT_VERSION)
START_TIME = time.time()


# ── Request/Response Models ───────────────────────────────────────────────────

class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Vera AI Bot is online! Base URL is active."}

@app.get("/v1/healthz")
def healthz():
    counts = store.counts()
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts_loaded": counts,
    }


@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": config.TEAM_NAME,
        "team_members": config.TEAM_MEMBERS,
        "model": f"{config.LLM_PROVIDER}/{config.LLM_MODEL or 'default'}",
        "approach": (
            "LLM-powered composition with trigger-dispatched prompts, "
            "rich 4-context injection, voice-profile enforcement, "
            "multi-turn conversation memory, and adaptive context handling."
        ),
        "contact_email": config.CONTACT_EMAIL,
        "version": config.BOT_VERSION,
        "submitted_at": config.SUBMITTED_AT,
    }


@app.post("/v1/context")
def push_context(body: ContextRequest, response: Response):
    accepted, reason, current_version = store.push(
        body.scope, body.context_id, body.version, body.payload
    )

    if not accepted:
        if reason == "stale_version":
            response.status_code = 409
            return {
                "accepted": False,
                "reason": "stale_version",
                "current_version": current_version,
            }
        response.status_code = 400
        return {"accepted": False, "reason": reason, "details": f"Unknown scope: {body.scope}"}

    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/tick")
def tick(body: TickRequest):
    actions = []
    deadline = time.time() + 15  # leave 15s buffer before 30s judge timeout

    for trigger_id in body.available_triggers:
        if time.time() > deadline:
            break  # stay within time budget
        if len(actions) >= config.MAX_ACTIONS_PER_TICK:
            break

        try:
            action = compose_tick(trigger_id)
            if action:
                actions.append(action)
        except Exception as e:
            # Log and continue — never crash the tick endpoint
            print(f"[WARN] compose_tick failed for {trigger_id}: {e}")
            continue

    return {"actions": actions}


@app.post("/v1/reply")
def reply(body: ReplyRequest):
    try:
        result = compose_reply(
            conv_id=body.conversation_id,
            merchant_id=body.merchant_id or "",
            customer_id=body.customer_id,
            merchant_message=body.message,
            turn_number=body.turn_number,
        )
    except Exception as e:
        print(f"[WARN] compose_reply failed: {e}")
        result = {
            "action": "send",
            "body": "Got it — let me follow up on that shortly.",
            "cta": "open_ended",
            "rationale": "Fallback reply due to internal error.",
        }

    # Clean up None values for clean JSON response
    return {k: v for k, v in result.items() if v is not None}


@app.post("/v1/teardown")
def teardown():
    store.teardown()
    conversation_manager.teardown()
    return {"status": "wiped"}


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
