# Reference Implementation Analysis

**Repository**: https://github.com/manishvat/magicpin-ai-challenge
**Files**: `main.py`, `store.py` (empty), `composer.py` (empty)
**Estimated Score**: ~80/100

---

## Architecture Overview

```
main.py (FastAPI, ~260 lines)
├── In-memory store: {category, merchant, customer, trigger}
├── Version tracker: {context_id → version}
├── compose_message() — rule-based string templates
├── /v1/tick — calls compose_message for each trigger
└── /v1/reply — keyword-matching for reply handling
```

Simple, flat, single-file implementation. No LLM.

---

## Strengths

### 1. Correct API Surface ✅
All 5 endpoints implemented and returning correct schema shapes. This is a prerequisite for any score — operational correctness fully met.

### 2. Idempotency Handling ✅
```python
old_version = versions.get(context_id, 0)
if version <= old_version:
    return {"accepted": False, "reason": "stale_version", ...}
```
Correctly handles version bumps and rejects stale re-posts.

### 3. Basic Trigger Routing ✅
Handles `research_digest`, `regulation_change`, `recall_due`, `perf_dip`, `renewal_due`, `wedding_package_followup`, `curious_ask_due` — covers the most common cases.

### 4. Auto-Reply Detection ✅
Phrase-based detection catches common WhatsApp Business auto-replies:
```python
auto_reply_phrases = ["thank you for contacting", "our team will respond", ...]
```

### 5. Intent Transition ✅
Basic keyword matching for positive responses:
```python
["yes", "ok", "okay", "lets do", "let's do", "send", "haan"]
```

### 6. Clean Exit for Hostility ✅
Recognizes stop/spam signals and ends conversation.

### 7. Customer Scope Handling ✅
`send_as = "merchant_on_behalf"` when customer context is present.

---

## Weaknesses (Why ~80, Not 90+)

### Critical Weakness 1: No LLM — Template Strings
```python
body = (
    f"Dr. {owner or name}, {item.get('source', 'this week's digest')} has one useful update: "
    f"{item.get('title', 'a new category insight')}. "
    f"{item.get('summary', '')[:130]} "
    f"Want me to turn this into a patient-friendly WhatsApp?"
)
```
**Problem**: Generic, repetitive, no natural language variation. The judge's LLM recognizes template-generated text and scores it lower on all dimensions.

### Critical Weakness 2: No Voice Differentiation
All categories get the same message tone. A dentist message and a restaurant message sound identical structurally. The `category.voice` profile is never read.

### Critical Weakness 3: Language Preference Ignored
No Hindi-English code-mix. Merchant language preferences (`["en", "hi"]`) are read but never applied.

### Critical Weakness 4: Shallow Merchant Context
Only uses: `name`, `owner_first_name`, one active offer. 

**Ignored**:
- `signals` — the most important derived context
- `conversation_history` — critical for avoiding repetition
- `customer_aggregate` — used in case studies ("your 124 high-risk adult patients")
- `review_themes` — rich personalization anchor
- `performance.delta_7d` — trend context, not just snapshot

### Critical Weakness 5: Generic Rationale
```python
"rationale": f"Composed using trigger kind '{kind}', merchant data, category voice, and available offer/context."
```
Same rationale for every message. The judge explicitly cross-checks rationale against message content — mismatch = penalty.

### Critical Weakness 6: No Peer Stat Comparison
Never uses `category.peer_stats` for comparison messages ("your CTR is 2.1% vs peer median 3.0%"). This is the most powerful specificity lever for perf-related triggers.

### Critical Weakness 7: template_params Always Empty
```python
"template_params": []
```
Non-compliant. Should extract key facts from the message body.

### Critical Weakness 8: No Conversation Memory in Reply
```python
def reply(data: dict):
    message = data.get("message", "").lower()
    # keyword matching only
```
No access to what was said before. Cannot continue the conversation naturally. A merchant asking "can you show me the abstract?" gets a generic response regardless of what Vera said initially.

### Critical Weakness 9: No Digest Trigger Coverage
Missing trigger kinds:
- `festival_upcoming` — uses default fallback
- `competitor_opened` — uses default fallback
- `milestone_reached` — uses default fallback
- `perf_spike` — uses default fallback
- `seasonal_perf_dip` — uses default fallback
- `active_planning_intent` — uses default fallback
- `gbp_unverified` — uses default fallback
- `supply_alert` — uses default fallback
- `chronic_refill_due` — uses default fallback
- `customer_lapsed_hard` — uses default fallback

The fallback is a generic CTR comparison message — highly irrelevant for these triggers.

### Critical Weakness 10: No Suppression Between Ticks
No tracking of which `suppression_key` values have already fired. In theory, the same trigger could be sent every tick.

---

## Score Breakdown Estimate

| Dimension | Score | Reason |
|---|---|---|
| Specificity | 7/10 | Has some numbers, no peer comparisons, no source citations |
| Category fit | 5/10 | No voice differentiation; dentists sound like restaurants |
| Merchant fit | 6/10 | Name + offer used; rich signals ignored |
| Trigger relevance | 8/10 | Core triggers routed correctly |
| Engagement compulsion | 7/10 | YES/STOP present; levers thin |
| **Total** | **33/50 → ~80 normalized** | |

---

## What We Copy

1. ✅ The idempotency/version logic (already correct)
2. ✅ The basic trigger routing structure (extended significantly)
3. ✅ The auto-reply phrase list (extended)
4. ✅ The suppression_key passthrough
5. ✅ The `send_as` logic for customer vs. merchant scope

## What We Build New

1. 🆕 LLM-powered composition with rich context injection
2. 🆕 Per-trigger-kind prompt templates
3. 🆕 Voice profile injection (category-specific tone enforcement)
4. 🆕 Hindi-English code-mix support
5. 🆕 Full merchant signal usage
6. 🆕 Peer stat comparison framing
7. 🆕 Conversation memory for multi-turn
8. 🆕 Semantic auto-reply + intent detection
9. 🆕 Coverage for all 20+ trigger kinds
10. 🆕 Contextual rationale generation
11. 🆕 Suppression tracking between ticks
12. 🆕 Adaptive context handling (version bumps incorporated immediately)
