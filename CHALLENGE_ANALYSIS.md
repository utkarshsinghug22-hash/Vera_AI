# Challenge Analysis — Magicpin Vera AI Challenge

## Overview

**Challenge**: Build an AI chatbot ("Vera") that engages and assists merchants on WhatsApp.
**Target Score**: 90+ out of 100 (normalized from 50-point rubric per evaluation).
**Reference Score**: ~80 (reference implementation).

---

## Core Mechanics

### The Composition Contract

```
compose(category, merchant, trigger, customer?) → message
```

Every message is built from **4 context layers**:

| Layer | Refresh | Key Contents |
|---|---|---|
| CategoryContext | Weekly | voice, offer_catalog, peer_stats, digest, seasonal_beats, trend_signals |
| MerchantContext | Daily/Realtime | identity, performance, offers, signals, conversation_history, customer_aggregate |
| TriggerContext | Per-event | kind, source, payload, urgency, suppression_key |
| CustomerContext | Per-interaction | relationship, state, preferences, consent |

### The 5 Scoring Dimensions (10 pts each = 50 total)

1. **Specificity** — Verifiable facts (numbers, dates, source citations)
2. **Category Fit** — Voice/vocabulary match for the business type
3. **Merchant Fit** — Personalized to this specific merchant's state
4. **Trigger Relevance** — Clear "why now" connected to the trigger
5. **Engagement Compulsion** — Would the merchant actually reply?

### The Testing Lifecycle

1. **Warmup** (T-15min): Base dataset (5 categories, 50 merchants, 200 customers) pushed to `/v1/context`
2. **Phase 2** (T+0 to T+60min): Triggers pushed, `/v1/tick` called every 5 simulated minutes
3. **Adaptive injection**: New digest items, updated perf, new triggers — bots that adapt score higher
4. **Replay test** (top 10 only): Auto-reply hell, intent transition, hostile scenarios

---

## Trigger Kind Taxonomy

### External Triggers
| Kind | Urgency | Strategy |
|---|---|---|
| `research_digest` | 2 | Source-cited, merchant-cohort anchored |
| `regulation_change` | 4 | Deadline-specific, actionable checklist offer |
| `festival_upcoming` | 1 | Category-specific prep angle |
| `competitor_opened` | 2 | Voyeur curiosity + counter-offer |
| `ipl_match_today` | 3 | Contrarian data (Saturday = -12% covers) |
| `category_seasonal` | 2 | Shelf-action / preparation angle |
| `cde_opportunity` | 1 | Peer-professional development |

### Internal Triggers
| Kind | Urgency | Strategy |
|---|---|---|
| `perf_dip` | 4 | Loss aversion + concrete recovery action |
| `perf_spike` | 1 | Reciprocity + attribution to recent action |
| `renewal_due` | 4 | ROI framing + days countdown |
| `milestone_reached` | 1 | Social proof + momentum |
| `dormant_with_vera` | 2 | Re-engagement, curiosity hook |
| `curious_ask_due` | 1 | Asking-the-merchant compulsion lever |
| `review_theme_emerged` | 3 | Specific quote + action |
| `seasonal_perf_dip` | 1 | Reframe expected dip, strategic advice |
| `active_planning_intent` | 4 | Direct action continuation (NO qualifying) |
| `winback_eligible` | 2 | Loss aversion + specific lapsed count |
| `gbp_unverified` | 3 | Concrete uplift percentage |

### Customer Triggers
| Kind | Urgency | Strategy |
|---|---|---|
| `recall_due` | 3 | Specific date, real slots, price anchor |
| `customer_lapsed_hard` | 3 | No-shame, past-goal alignment |
| `chronic_refill_due` | 3 | Molecule-specific, senior-friendly |
| `trial_followup` | 2 | Momentum from trial experience |
| `wedding_package_followup` | 2 | Days countdown, window urgency |

---

## Compulsion Levers (Priority Order)

1. **Specificity/verifiability** — concrete numbers stop the scroll
2. **Loss aversion** — "you're missing X" / "before window closes"
3. **Asking-the-merchant** — massively underused, high engagement
4. **Social proof** — "3 dentists in your locality did Y this month"
5. **Effort externalization** — "I've drafted X, just say go"
6. **Curiosity** — "want to see who?" / "want the full list?"
7. **Reciprocity** — "I noticed Y, thought you'd want to know"
8. **Single binary CTA** — YES/STOP reduces friction

---

## Critical Anti-Patterns to Avoid

| Anti-Pattern | Penalty |
|---|---|
| Generic "10% off" offers | Specificity -3 |
| Multiple CTAs | Engagement -2 |
| Buried CTA | Engagement -1 |
| Promotional tone for clinical categories | Category fit -3 |
| Hallucinated data | Catastrophic — cap at 5/10 per dimension |
| Long preambles | All dimensions -1 |
| Re-introducing Vera after turn 1 | Merchant fit -1 |
| Ignoring language preference | Merchant fit -2 |
| Verbatim repeat | -2 operational penalty |
| URLs in message body | -3 operational penalty |

---

## What Scores 90+ vs 80

| Capability | ~80 Reference | 90+ Target |
|---|---|---|
| Message composition | Rule-based templates | LLM with full context |
| Voice differentiation | None | Per-category voice injection |
| Language preference | Ignored | Hindi-English mix honored |
| Specificity | Merchant name + one stat | All signals + peer stats + digest |
| Rationale quality | Generic one-liner | Contextual, matches the message |
| Multi-turn reply | Keyword matching | LLM with conversation history |
| Auto-reply detection | Basic keyword | Pattern + similarity + counter |
| Intent detection | Basic keywords | Semantic classification |
| Trigger coverage | 6-7 kinds | All 20+ trigger kinds |
| Adaptive context | Not handled | Updates applied immediately |

---

## Adaptation Strategy for Phase 3 Injection

The judge injects:
- New digest items (version bump on category)
- Updated merchant perf snapshots (version bump on merchant)
- 15 new triggers
- 5 customer contexts with recall_due triggers

Our bot must:
1. Accept version bumps atomically (`/v1/context` idempotency)
2. Use latest version in all subsequent compositions
3. Explicitly reference new digest items when composing

---

## Scoring the Reference at ~80

| Dimension | Estimated Score | Why |
|---|---|---|
| Specificity | 6.5/10 | Has numbers, no source citations, no peer stat comparisons |
| Category fit | 5.5/10 | No voice differentiation; clinical categories get retail tone |
| Merchant fit | 6/10 | Name used; misses signals, language pref, history |
| Trigger relevance | 8/10 | Good trigger routing, clear "why now" |
| Engagement compulsion | 7/10 | YES/STOP CTA always present; compulsion levers thin |
| **Average** | **6.6 × 10 = ~66** | **Normalized to ~80 on their scale** |

Biggest gaps: category fit and merchant fit — both fixable with LLM + rich context injection.
