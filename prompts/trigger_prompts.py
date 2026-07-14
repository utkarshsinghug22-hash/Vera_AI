"""Trigger prompt builders."""

def build_prompt(category, merchant, trigger, customer=None):
    identity = merchant.get("identity", {})
    owner = identity.get("owner_first_name", "")
    name = identity.get("name", "your business")
    salutation = f"Dr. {owner}" if category.get("slug") == "dentists" and owner else owner or name
    langs = identity.get("languages", ["en"])
    lang_note = "Use natural Hindi-English mix (Hinglish)" if "hi" in langs else "Write in English"
    
    perf = merchant.get("performance", {})
    peer = category.get("peer_stats", {})
    offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
    offer_text = offers[0]["title"] if offers else "your active offer"
    signals = merchant.get("signals", [])
    cust_agg = merchant.get("customer_aggregate", {})
    conv_hist = merchant.get("conversation_history", [])
    last_touch = conv_hist[-1]["body"][:80] if conv_hist else "no prior conversation"
    
    voice = category.get("voice", {})
    taboos = voice.get("vocab_taboo", [])
    tone = voice.get("tone", "professional")
    
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})
    urgency = trigger.get("urgency", 2)

    base_ctx = f"""CATEGORY: {category.get("slug", "unknown")}
Voice/tone: {tone}. Avoid: {", ".join(taboos[:5]) if taboos else "none"}.
Peer stats: avg_ctr={peer.get("avg_ctr", "N/A")}, avg_reviews={peer.get("avg_review_count", "N/A")}

MERCHANT: {name}
Salutation to use: {salutation}
Language rule: {lang_note}
Performance (30d): views={perf.get("views","?")}, calls={perf.get("calls","?")}, CTR={perf.get("ctr","?")} (peer avg CTR={peer.get("avg_ctr","?")})
7d delta: {perf.get("delta_7d", {})}
Active offer: {offer_text}
Signals: {", ".join(signals) if signals else "none"}
Customer aggregate: {cust_agg}
Last Vera touch: {last_touch}

TRIGGER kind={kind}, urgency={urgency}/5
Payload: {payload}
"""

    if kind == "research_digest":
        item_id = payload.get("top_item_id")
        item = next((d for d in category.get("digest", []) if d.get("id") == item_id), {})
        return base_ctx + f"""
DIGEST ITEM:
Title: {item.get("title", "N/A")}
Source: {item.get("source", "N/A")}
Trial N: {item.get("trial_n", "N/A")}
Segment: {item.get("patient_segment", "N/A")}
Summary: {item.get("summary", "N/A")}
Actionable: {item.get("actionable", "N/A")}

INSTRUCTIONS:
1. Open with source + key finding (not "Hi {salutation}")
2. Anchor on their specific patient cohort from customer_aggregate
3. Offer to pull abstract + draft a patient-ed WhatsApp
4. CTA: open_ended (curious question)
5. Max 3 sentences. Cite source. No URLs.
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "regulation_change":
        item_id = payload.get("top_item_id")
        item = next((d for d in category.get("digest", []) if d.get("id") == item_id), {})
        deadline = payload.get("deadline_iso", "")
        return base_ctx + f"""
COMPLIANCE ITEM:
Title: {item.get("title", "N/A")}
Source: {item.get("source", "N/A")}
Summary: {item.get("summary", "N/A")}
Actionable: {item.get("actionable", "N/A")}
Deadline: {deadline}

INSTRUCTIONS:
1. Urgency first — name the regulation + deadline
2. Give specific actionable (from item.actionable)
3. Offer to draft a compliance checklist
4. CTA: binary_yes_no
5. Max 3 sentences. Cite source. No URLs.
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "perf_dip":
        metric = payload.get("metric", "calls")
        delta = int(abs(payload.get("delta_pct", 0) * 100))
        window = payload.get("window", "7d")
        is_seasonal = payload.get("is_expected_seasonal", False)
        return base_ctx + f"""
DIP DATA:
Metric: {metric} dropped {delta}% in {window}
Expected seasonal: {is_seasonal}

INSTRUCTIONS:
{"1. Reframe as normal seasonal dip (give peer range). Advise saving ad spend for peak season." if is_seasonal else "1. Frame as loss aversion — specific % drop is alarming but recoverable."}
2. Reference their actual CTR vs peer CTR gap if relevant
3. Offer one concrete recovery action using their active offer
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "perf_spike":
        metric = payload.get("metric", "calls")
        delta = int(payload.get("delta_pct", 0) * 100)
        driver = payload.get("likely_driver", "")
        return base_ctx + f"""
SPIKE DATA: {metric} up {delta}% in {payload.get("window","7d")}. Likely driver: {driver}

INSTRUCTIONS:
1. Celebrate the spike with reciprocity ("I noticed X is working")
2. Attribute to likely driver if available
3. Suggest capitalising — post or offer to lock in the momentum
4. CTA: open_ended
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "renewal_due":
        days = payload.get("days_remaining", 14)
        amount = payload.get("renewal_amount", "")
        plan = payload.get("plan", "Pro")
        return base_ctx + f"""
RENEWAL: {plan} plan, {days} days left{f", ₹{amount}" if amount else ""}
INSTRUCTIONS:
1. Loss aversion: what stops working when subscription expires
2. Show ROI from last 30d (views, calls from perf data)
3. Make renewal feel easy (low-friction)
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "festival_upcoming":
        festival = payload.get("festival", "upcoming festival")
        days_until = payload.get("days_until", 7)
        return base_ctx + f"""
FESTIVAL: {festival} in {days_until} days
INSTRUCTIONS:
1. Category-specific festival angle (not generic "happy festival")
2. Connect to their active offer or create a festival variant
3. Effort externalization: offer to draft a GBP post + WhatsApp
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "competitor_opened":
        comp = payload.get("competitor_name", "a competitor")
        dist = payload.get("distance_km", "nearby")
        their_offer = payload.get("their_offer", "lower prices")
        return base_ctx + f"""
COMPETITOR: {comp} opened {dist}km away, offering {their_offer}
INSTRUCTIONS:
1. Voyeur curiosity hook ("want to see what they're offering?")
2. Differentiate on their strengths (reviews, established year, quality signals)
3. Suggest a counter-positioning offer or GBP post
4. CTA: open_ended (curiosity)
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "curious_ask_due":
        return base_ctx + f"""
INSTRUCTIONS:
1. Ask one specific, low-stakes question about their business
2. Offer to turn the answer into something useful (GBP post, WhatsApp draft)
3. Frame the effort as <5 minutes
4. CTA: open_ended
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "milestone_reached":
        metric = payload.get("metric", "reviews")
        val = payload.get("value_now", "")
        milestone = payload.get("milestone_value", "")
        return base_ctx + f"""
MILESTONE: {metric} approaching {milestone} (currently {val})
INSTRUCTIONS:
1. Create anticipation ("you're X away from {milestone}")
2. Social proof: what hitting {milestone} means for visibility
3. Offer to draft a celebratory GBP post ready to publish when hit
4. CTA: open_ended
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "review_theme_emerged":
        theme = payload.get("theme", "")
        count = payload.get("occurrences_30d", 0)
        trend = payload.get("trend", "")
        quote = payload.get("common_quote", "")
        return base_ctx + f"""
REVIEW THEME: "{theme}" mentioned {count}x in 30d (trend: {trend})
Sample quote: "{quote}"
INSTRUCTIONS:
1. Name the pattern specifically (not "some reviews mention X")
2. Frame as both risk and opportunity
3. Offer a specific fix (response template or operational tweak)
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "active_planning_intent":
        topic = payload.get("intent_topic", "")
        last_msg = payload.get("merchant_last_message", "")
        return base_ctx + f"""
PLANNING INTENT: Merchant wants to plan "{topic}"
Their exact words: "{last_msg}"

INSTRUCTIONS:
*** CRITICAL: Do NOT ask qualifying questions. Merchant already committed. ***
1. Immediately provide the drafted artifact (pricing, structure, copy)
2. Be specific — use their locality, their category norms, their existing offers
3. Offer the next concrete step
4. CTA: open_ended or binary_yes_no
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    if kind == "winback_eligible":
        days = payload.get("days_since_expiry", 30)
        dip = int(abs(payload.get("perf_dip_pct", 0) * 100))
        lapsed = payload.get("lapsed_customers_added_since_expiry", 0)
        return base_ctx + f"""
WINBACK: Subscription expired {days} days ago, perf down {dip}%, {lapsed} customers lapsed since
INSTRUCTIONS:
1. Loss aversion: quantify what they've lost since expiry
2. Make comeback feel achievable and low-friction
3. Offer a quick-win first step
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "gbp_unverified":
        uplift = int(payload.get("estimated_uplift_pct", 0.30) * 100)
        return base_ctx + f"""
GBP UNVERIFIED: estimated {uplift}% uplift from verification
INSTRUCTIONS:
1. Quantify the missed opportunity (uplift % + peer comparison)
2. Make process sound easy (postcard or phone call)
3. Offer to walk them through it
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "supply_alert":
        molecule = payload.get("molecule", "")
        batches = payload.get("affected_batches", [])
        mfr = payload.get("manufacturer", "")
        chronic_count = cust_agg.get("chronic_rx_count", 0)
        return base_ctx + f"""
SUPPLY ALERT: Voluntary recall on {molecule}, batches {batches}, by {mfr}
Merchant has {chronic_count} chronic Rx customers
INSTRUCTIONS:
1. Urgency first: name molecule + batch numbers + manufacturer
2. Estimate how many of their customers are affected (derive from chronic_rx_count)
3. Offer to draft customer notification + replacement workflow
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "ipl_match_today":
        match = payload.get("match", "IPL match")
        venue = payload.get("venue", "")
        is_weeknight = payload.get("is_weeknight", True)
        return base_ctx + f"""
IPL: {match} at {venue}, weeknight={is_weeknight}
INSTRUCTIONS:
{"1. Promote match-night special using active offer (weeknight = footfall boost)" if is_weeknight else "1. COUNTER-INTUITIVE: Saturday IPL = -12% restaurant covers (people watch at home). Recommend delivery push instead."}
2. Use operator-to-operator language (covers, AOV)
3. Offer to draft Swiggy banner / Insta story
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "category_seasonal":
        season = payload.get("season", "")
        trends = payload.get("trends", [])
        return base_ctx + f"""
SEASONAL TREND: {season}
Demand shifts: {", ".join(trends)}
INSTRUCTIONS:
1. Lead with the most actionable demand shift (highest delta)
2. Connect to their specific inventory/offers
3. Suggest shelf action or offer update
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "cde_opportunity":
        item_id = payload.get("digest_item_id", "")
        item = next((d for d in category.get("digest", []) if d.get("id") == item_id), {})
        credits = payload.get("credits", 0)
        fee = payload.get("fee", "")
        return base_ctx + f"""
CDE: {item.get("title","Webinar")} — {credits} credits, {fee}
Summary: {item.get("summary","")}
INSTRUCTIONS:
1. Peer-professional framing (colleague telling colleague)
2. Highlight the credit value + speaker credibility
3. Make registration sound effortless
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    # CUSTOMER TRIGGERS
    if kind == "recall_due" and customer:
        cid = customer.get("identity", {})
        cname = cid.get("name", "there")
        lang = cid.get("language_pref", "english")
        lang_note2 = "Use natural Hindi-English mix" if "hi" in lang else f"Use {lang}"
        slots = payload.get("available_slots", [])
        slot_text = " or ".join(s["label"] for s in slots[:2]) if slots else "this week"
        svc = payload.get("service_due", "follow-up").replace("_", " ")
        prefs = customer.get("preferences", {})
        slot_pref = prefs.get("preferred_slots", "")
        return base_ctx + f"""
CUSTOMER RECALL:
Customer: {cname}, language: {lang} ({lang_note2})
State: {customer.get("state","")}
Last visit: {customer.get("relationship",{}).get("last_visit","")}
Service due: {svc}
Available slots: {slot_text} (matches pref: {slot_pref})
Active offer: {offer_text}

INSTRUCTIONS:
send_as = merchant_on_behalf (from merchant's WA number, NOT from Vera)
1. Greeting from the clinic/merchant (not Vera)
2. Name the recall window explicitly (X months since last visit)
3. Offer specific slots matching their preference
4. Include offer price
5. Clear CTA: multi_choice_slot
Return JSON: {{"body":"...","cta":"multi_choice_slot","rationale":"..."}}"""

    if kind == "customer_lapsed_hard" and customer:
        cid = customer.get("identity", {})
        cname = cid.get("name", "there")
        days = payload.get("days_since_last_visit", 60)
        focus = payload.get("previous_focus", "")
        months = payload.get("previous_membership_months", 0)
        return base_ctx + f"""
CUSTOMER LAPSE:
Customer: {cname}, {days} days since last visit, {months} months prior membership
Their focus: {focus}
INSTRUCTIONS (send_as=merchant_on_behalf):
1. No-shame opening ("happens to most members")
2. Reference their specific goal ({focus})
3. New offering that matches their goal
4. No-commitment trial offer, single CTA
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "chronic_refill_due" and customer:
        cid = customer.get("identity", {})
        cname = cid.get("name", "there")
        mols = payload.get("molecule_list", [])
        runs_out = payload.get("stock_runs_out_iso", "")[:10]
        delivery = payload.get("delivery_address_saved", False)
        senior = cid.get("senior_citizen", False)
        lang = cid.get("language_pref", "hi")
        return base_ctx + f"""
REFILL DUE:
Customer: {cname}, senior={senior}, language={lang}
Molecules: {", ".join(mols)}
Runs out: {runs_out}
Delivery address saved: {delivery}
Active offers: {offer_text}

INSTRUCTIONS (send_as=merchant_on_behalf):
1. Respectful opening (Namaste for Hindi/senior)
2. Name the molecules explicitly
3. Show savings (senior discount if applicable)
4. One-tap confirm CTA
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "trial_followup" and customer:
        cid = customer.get("identity", {})
        cname = cid.get("name", "there")
        trial_date = payload.get("trial_date", "")
        next_opts = payload.get("next_session_options", [])
        slot_text = next_opts[0]["label"] if next_opts else "next available slot"
        return base_ctx + f"""
TRIAL FOLLOWUP:
Customer: {cname}, trial on {trial_date}
Next slot: {slot_text}
INSTRUCTIONS (send_as=merchant_on_behalf):
1. Reference trial by name + date
2. Offer the next concrete step (book the next session)
3. Low-friction single CTA
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "wedding_package_followup" and customer:
        cid = customer.get("identity", {})
        cname = cid.get("name", "there")
        wedding_date = payload.get("wedding_date", "")
        days_to = payload.get("days_to_wedding", 0)
        next_step = payload.get("next_step_window_open", "").replace("_", " ")
        prefs = customer.get("preferences", {})
        pref_slot = prefs.get("preferred_slots", "")
        return base_ctx + f"""
BRIDAL FOLLOWUP:
Customer: {cname}, wedding {wedding_date} ({days_to} days away)
Next step window: {next_step}
Preferred slot: {pref_slot}
INSTRUCTIONS (send_as=merchant_on_behalf):
1. Days countdown creates urgency
2. This is the right prep window — explain why
3. Offer to block their preferred slot for next session
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""

    if kind == "dormant_with_vera":
        days = payload.get("days_since_last_merchant_message", 30)
        last_topic = payload.get("last_topic", "")
        return base_ctx + f"""
DORMANT: {days} days since last merchant message, last topic was "{last_topic}"
INSTRUCTIONS:
1. Re-engage with something genuinely useful (not "just checking in")
2. Pick the most relevant signal from their context
3. Curiosity hook or quick win offer
4. CTA: open_ended
Return JSON: {{"body":"...","cta":"open_ended","rationale":"..."}}"""

    # Default fallback
    ctr_gap = ""
    peer_ctr = peer.get("avg_ctr")
    my_ctr = perf.get("ctr")
    if peer_ctr and my_ctr:
        gap = round((peer_ctr - my_ctr) / peer_ctr * 100)
        if gap > 0:
            ctr_gap = f" (peer avg {peer_ctr:.1%}, yours {my_ctr:.1%} — {gap}% gap)"

    return base_ctx + f"""
TRIGGER kind={kind} — use the payload data to determine the most relevant message.
CTR gap: {ctr_gap}
INSTRUCTIONS:
1. Use the most specific data point from the trigger payload
2. Reference their signals and active offer
3. One concrete next step
4. CTA: binary_yes_no
Return JSON: {{"body":"...","cta":"binary_yes_no","rationale":"..."}}"""
