# Architecture — Vera Bot (Production Implementation)

## High-Level Design

```
                    ┌─────────────────────────────────┐
                    │      magicpin Judge Harness      │
                    │  ─── HTTP/JSON ──►               │
                    └──────────┬──────────────────────┘
                               │
                    ┌──────────▼──────────────────────┐
                    │         FastAPI App (main.py)    │
                    │   /v1/healthz  /v1/metadata      │
                    │   /v1/context  /v1/tick          │
                    │   /v1/reply    /v1/teardown      │
                    └──────┬──────────────┬────────────┘
                           │              │
              ┌────────────▼──┐    ┌──────▼──────────┐
              │  Context Store │    │ Conversation Mgr │
              │  (core/store) │    │ (core/convo)     │
              │  - categories  │    │ - history/turns  │
              │  - merchants   │    │ - auto-reply cnt │
              │  - customers   │    │ - intent state   │
              │  - triggers    │    │ - suppressed ids  │
              └────────────┬──┘    └──────┬────────────┘
                           │              │
                    ┌──────▼──────────────▼────────────┐
                    │        Composer (composer/)       │
                    │  1. Build rich context snapshot   │
                    │  2. Route to trigger-kind prompt  │
                    │  3. LLM call with system prompt   │
                    │  4. Validate + repair output      │
                    └──────────────┬────────────────────┘
                                   │
                    ┌──────────────▼────────────────────┐
                    │       LLM Client (services/)      │
                    │   Gemini 2.0 Flash (primary)      │
                    │   GPT-4o-mini (fallback)          │
                    └───────────────────────────────────┘
```

---

## Module Breakdown

### `main.py` — FastAPI Application
- **5 endpoints** + optional `/v1/teardown`
- Delegates all logic to modules
- Returns responses within 30s budget
- Thread-safe (uses FastAPI async where possible)

### `core/store.py` — Context Store
```python
class ContextStore:
    def push(scope, context_id, version, payload) → Ack
    def get(scope, context_id) → payload | None
    def get_all(scope) → {id: payload}
    def get_merchant_with_category(merchant_id) → (merchant, category)
```
- In-memory dict with version tracking
- Idempotent: same version = 409, higher version = replace
- Thread-safe with `threading.Lock`

### `core/conversation.py` — Conversation Manager
```python
class ConversationManager:
    def add_turn(conv_id, role, body, ts) → None
    def get_history(conv_id) → [Turn]
    def get_auto_reply_count(conv_id) → int
    def increment_auto_reply(conv_id) → None
    def is_suppressed(conv_id) → bool
    def suppress(conv_id) → None
    def get_fired_suppressions() → Set[str]
    def mark_suppression_fired(key) → None
```
- Per-conversation turn history
- Auto-reply counter per conversation
- Global suppression key tracking

### `composer/composer.py` — Main Composer
```python
class VeraComposer:
    def compose_tick(trigger_id, merchant, category, trigger, customer) → Action
    def compose_reply(conv_id, merchant_id, merchant_msg, turn_number) → ReplyAction
```

**Tick flow**:
1. Check if suppression key already fired → skip if yes
2. Build context snapshot (merchant + category + trigger + customer)
3. Route to trigger-kind prompt
4. Call LLM with system prompt + trigger prompt
5. Parse + validate response
6. Return action dict

**Reply flow**:
1. Fetch conversation history
2. Detect auto-reply → handle with counter
3. Detect hostile → end
4. Detect intent transition → action mode
5. Build context-aware reply prompt
6. Call LLM
7. Return reply action

### `composer/trigger_router.py` — Prompt Dispatch
```python
TRIGGER_PROMPTS = {
    "research_digest": build_research_digest_prompt,
    "regulation_change": build_regulation_change_prompt,
    "perf_dip": build_perf_dip_prompt,
    "perf_spike": build_perf_spike_prompt,
    "recall_due": build_recall_due_prompt,
    "renewal_due": build_renewal_due_prompt,
    "festival_upcoming": build_festival_prompt,
    "competitor_opened": build_competitor_prompt,
    "curious_ask_due": build_curious_ask_prompt,
    "milestone_reached": build_milestone_prompt,
    "review_theme_emerged": build_review_theme_prompt,
    "seasonal_perf_dip": build_seasonal_dip_prompt,
    "active_planning_intent": build_planning_intent_prompt,
    "winback_eligible": build_winback_prompt,
    "gbp_unverified": build_gbp_unverified_prompt,
    "supply_alert": build_supply_alert_prompt,
    "chronic_refill_due": build_chronic_refill_prompt,
    "customer_lapsed_hard": build_lapse_winback_prompt,
    "trial_followup": build_trial_followup_prompt,
    "wedding_package_followup": build_bridal_followup_prompt,
    "cde_opportunity": build_cde_prompt,
    "ipl_match_today": build_ipl_prompt,
    "category_seasonal": build_category_seasonal_prompt,
}
```

### `prompts/system.py` — Master System Prompt
Encodes:
- Vera's persona and mission
- The 5 scoring dimensions (injected directly)
- Anti-patterns to avoid
- Compulsion lever hierarchy
- Output format (strict JSON)
- Fabrication prohibition

### `prompts/trigger_prompts.py` — Per-Kind Prompt Builders
Each builder:
- Accepts `(category, merchant, trigger, customer?)` as input
- Pre-computes key numbers (delta percentages, peer comparisons)
- Injects category voice profile + taboos
- Returns a detailed user prompt for the LLM

### `services/llm_client.py` — LLM Abstraction
```python
class LLMClient:
    def complete(system_prompt, user_prompt, temperature=0) → str
    def _call_gemini(...)
    def _call_openai(...)
    def _call_anthropic(...)
```
- Primary: Google Gemini 2.0 Flash (fast, free)
- Fallback: GPT-4o-mini or Anthropic Claude
- Retry logic: 2 retries with backoff
- Timeout: 25s (leaves 5s buffer for judge's 30s limit)

### `utils/auto_reply_detector.py`
```python
def is_auto_reply(message: str) -> bool:
    """Multi-signal detection:
    1. Phrase matching (expanded list from challenge examples)
    2. Structural patterns (formulaic acknowledgment)
    3. No question or call-to-action in message
    """
```

### `utils/intent_detector.py`
```python
def detect_intent(message: str) -> Literal["commit", "reject", "question", "off_topic", "unknown"]:
    """Intent classification:
    - commit: "ok let's do it", "yes please", "go ahead", "haan karo"
    - reject: "stop", "not interested", "spam", "band karo"
    - question: "?", "how", "what", "kya", "kitna"
    - off_topic: GST, unrelated topics
    - unknown: unclear
    """
```

---

## Data Flow — Tick Endpoint

```
POST /v1/tick
  { now, available_triggers: ["trg_001", "trg_002"] }
  
  for each trigger_id:
    1. Load trigger from store
    2. Load merchant + category from store
    3. Load customer if trigger.customer_id
    4. Check suppression_key not already fired
    5. Composer.compose_tick(...)
       a. Build context snapshot
       b. Route to prompt builder
       c. LLM call (≤25s)
       d. Parse JSON response
       e. Validate: CTA shape, no URL, no repeat
    6. Mark suppression_key fired
    7. Append to actions[]
    
  return { actions }
```

## Data Flow — Reply Endpoint

```
POST /v1/reply
  { conversation_id, merchant_id, from_role, message, turn_number }
  
  1. Load conversation history
  2. is_auto_reply(message)?
     - count ≤ 1: send "looks like auto-reply" nudge + wait
     - count == 2: wait 24h
     - count ≥ 3: end
  3. detect_intent(message)?
     - commit: action mode (draft artifact immediately)
     - reject: end gracefully
     - off_topic: redirect politely + continue
     - question/unknown: LLM reply with history context
  4. LLM reply composition
  5. Return { action, body, cta, rationale }
```

---

## Prompt Architecture — Example (research_digest)

**System prompt** (truncated):
```
You are Vera, magicpin's merchant AI assistant. You compose WhatsApp messages.

SCORING (be aware — your output will be judged on these):
- Specificity: cite exact numbers, dates, sources from the context
- Category fit: match voice profile exactly
- Merchant fit: use their name, their signals, their language preference
- Trigger relevance: make the "why now" central, not an afterthought
- Engagement compulsion: end with a single, low-friction ask

ANTI-PATTERNS (any of these lose points):
- Generic "X% off" framing
- Multiple CTAs
- Long preambles
- Re-introducing yourself after turn 1
- URLs in the message body
- Hallucinating data not in the context

OUTPUT FORMAT (strict JSON):
{ "body": "...", "cta": "open_ended|binary_yes_no|none", "rationale": "..." }
```

**User prompt** (research_digest):
```
COMPOSE a WhatsApp message for this scenario:

CATEGORY: dentists
Voice: peer_clinical, collegial. Use: fluoride varnish, caries, IOPA. Avoid: guaranteed, miracle.
Peer stats: avg_ctr=3.0%, avg_reviews=62

MERCHANT: Dr. Meera's Dental Clinic, Lajpat Nagar, Delhi
Owner: Meera
Language: hi-en mix (blend Hindi and English naturally)
Performance: CTR=2.1% (BELOW peer 3.0% — cite this gap)
Signals: stale_posts:22d, ctr_below_peer_median, high_risk_adult_cohort
Customer aggregate: 124 high-risk adults in roster, 78 lapsed >180d
Active offer: Dental Cleaning @ ₹299
Last Vera touch: 2d ago, merchant replied

TRIGGER: research_digest (external, urgency=2)
Digest item: "3-month fluoride varnish recall outperforms 6-month for high-risk adult caries"
Source: JIDA Oct 2026, p.14
Trial: 2,100 patients, 38% lower caries recurrence, high-risk adults segment

INSTRUCTIONS:
1. Lead with the source + finding (not "Hi Meera")
2. Anchor on "your high-risk adult patients" (she has 124 — cite this)
3. Offer to do something (pull the abstract + draft patient WhatsApp)
4. CTA: open_ended (question, not YES/STOP — this is information)
5. 2-3 sentences max. No URLs.

Return JSON: { "body": "...", "cta": "open_ended", "rationale": "..." }
```

---

## Configuration

```python
# config.py
LLM_PROVIDER = "gemini"           # gemini | openai | anthropic
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = "gemini-2.0-flash-exp"
LLM_TIMEOUT = 25
LLM_TEMPERATURE = 0              # deterministic
MAX_BODY_LENGTH = 600            # soft cap; judges on quality not length
PORT = 8080
```

---

## Performance Budget

| Operation | Budget | Actual |
|---|---|---|
| `/v1/context` | 5s | <100ms (in-memory) |
| `/v1/healthz` | 2s | <10ms |
| `/v1/tick` | 30s | ~3-8s per LLM call |
| `/v1/reply` | 30s | ~2-5s per LLM call |

For tick with many triggers: process in serial (cap at 5 per tick), return early if approaching 28s threshold.
