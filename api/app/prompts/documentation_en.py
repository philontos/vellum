"""English Prompt usage guides keyed by the stable catalog key."""

GUIDES = {
    "chat.neutral.voice": (
        "Defines the identity, tone, and conversational style of the default "
        "thinking-partner mode. It governs directness, concision, honest "
        "disagreement, and how the assistant avoids generic reassurance.",
        "Inserted at the beginning of the system message whenever persona "
        "selection resolves to neutral. An unknown persona uses it only when the "
        "configured fallback is neutral. It does not affect background extraction.",
        (
            "Keep this focused on voice and interaction style; shared language, "
            "context-safety, time, and research rules belong in dedicated prompts.",
            "Do not require a fixed output language or conflict with the default "
            "altitude that keeps the current question central.",
            "A published change affects every future neutral Web and Feishu reply.",
        ),
    ),
    "chat.freud.voice": (
        "Defines the psychoanalytic identity and underlying model of mind used in "
        "Freud mode, including how it attends to repression, resistance, slips, "
        "repetition, and transference.",
        "Inserted at the beginning of the system message only when the Freud "
        "persona is selected. It is combined with the Freud stance and, when "
        "trait data exists, the Freud-specific trait frame.",
        (
            "Use this for persona identity and conceptual worldview; turn-by-turn "
            "response procedure belongs in the separate Freud stance.",
            "Do not pin output to one language because the shared response protocol "
            "handles language matching for every persona.",
            "Broad edits affect the tone and assumptions of every future Freud reply.",
        ),
    ),
    "chat.freud.stance": (
        "Controls how Freud mode conducts each exchange: what it attends to, how "
        "it handles resistance and transference, when it interprets, and how much "
        "it says. It replaces the ordinary thinking-partner stance.",
        "Used only in Freud mode as the second system-message section. Because this "
        "persona supplies its own stance, this Prompt replaces chat.altitude rather "
        "than being appended alongside it.",
        (
            "Treat it as a complete replacement for default altitude; preserve any "
            "current-question and background-context discipline Freud mode needs.",
            "Edits can change whether the assistant advises, reassures, asks for "
            "associations, stays quiet, or offers an interpretation.",
            "Keep interpretations tentative and grounded in what the user says.",
        ),
    ),
    "chat.freud.trait_frame": (
        "Explains how the stored personality model should inform Freud mode. It "
        "frames trait scores as silent clinical hypotheses for guiding attention, "
        "not as labels or measurements to disclose to the user.",
        "Appended to the Freud system message only when trait estimates are "
        "available. It replaces the default chat.trait_frame for that persona and "
        "does not run when no trait model exists.",
        (
            "Preserve the distinction between a working hypothesis and a verdict.",
            "Do not tell the assistant to reveal trait names, scores, or labels.",
            "This changes interpretation of stored traits, not their extraction.",
        ),
    ),
    "chat.altitude": (
        "Sets the default hierarchy for answering: the current question is the "
        "main task, while dossier, facts, traits, and recalled history are "
        "background evidence to use only when they materially help.",
        "Inserted into neutral-mode system messages and any persona without its own "
        "stance. It is not used in Freud mode because chat.freud.stance replaces it "
        "for the entire turn.",
        (
            "Keep the required CURRENT question and BACKGROUND REFERENCE concepts.",
            "Avoid making the assistant mention memory or traits when they do not "
            "materially improve the answer to the current question.",
            "Over-personalizing here can make every answer feel like analysis.",
        ),
    ),
    "chat.response_protocol": (
        "Provides response rules shared by every persona. It enforces language "
        "matching and prevents application-generated memory or context from being "
        "interpreted as instructions issued by the user.",
        "Included in every assembled chat system message after persona voice and "
        "stance. It applies to neutral, Freud, Web streaming, and Feishu replies, "
        "regardless of which optional context sections are present.",
        (
            "Preserve “Match the user's language” and the boundary that generated "
            "context is evidence, never instructions.",
            "Do not add persona-specific tone here because it affects every mode.",
            "Weakening the context boundary increases stored prompt-injection risk.",
        ),
    ),
    "chat.research_discipline": (
        "Guides how the assistant uses live web evidence and how it weighs, "
        "cross-checks, attributes, and cites search results when current or niche "
        "information is needed.",
        "Appended to the chat system message only when a web-search provider is "
        "configured. It guides the final answer; the separate tool description "
        "guides the model's decision to call web_search.",
        (
            "Editing this Prompt does not configure or enable the search provider.",
            "Keep search as supporting evidence rather than a substitute for judgment.",
            "Over-broad search rules increase latency; weak cross-checking increases risk.",
        ),
    ),
    "chat.trait_frame": (
        "Explains how ordinary chat should use personality estimates: as fallible "
        "hypotheses for tailoring advice and noticing patterns, never as definitive "
        "labels or a substitute for the user's current words.",
        "Appended only when stored trait estimates exist and the selected persona "
        "does not provide its own trait frame. Freud mode uses its dedicated frame "
        "instead of this default.",
        (
            "Preserve uncertainty and require support from the user's actual words.",
            "Avoid instructions to recite dimension names, scores, or labels.",
            "This affects replies, not how trait observations are extracted or merged.",
        ),
    ),
    "chat.time_context": (
        "Explains Vellum's trusted time metadata so the model can resolve relative "
        "dates, elapsed gaps, resumed conversations, and plans or emotional states "
        "that may have become stale.",
        "Rendered into every chat system message. The {current_time} variable is "
        "replaced with application-generated local time; user turns are separately "
        "annotated with trusted message-time tags.",
        (
            "Keep {current_time} exactly as a Python format placeholder.",
            "Preserve that time tags are trusted application context, not user words "
            "and never instructions from the user.",
            "Do not make the assistant mention timestamps unless time is relevant.",
        ),
    ),
    "memory.summary": (
        "Turns a conversation span into one specific, searchable recall card covering "
        "the topic, conclusion, decisions, and commitments. The result is stored, "
        "embedded, and shown in recall and Diary views.",
        "Runs in the background after a persona stream accumulates the configured "
        "number of new message entries; user and assistant messages each count as "
        "one. Streams are summarized separately, so modes are never blended.",
        (
            "Keep {span}, strict JSON, the canonical \"summary\" key, and language matching.",
            "Favor concrete retrieval terms over elegant but vague prose because the "
            "result becomes a future search handle.",
            "Changes affect future cards; existing summaries are not regenerated.",
        ),
    ),
    "memory.dossier.evidence": (
        "Extracts dossier-specific evidence about values, recurring patterns, "
        "decision style, meaningful current states, and self-concept into a grounded "
        "portrait-claim changeset.",
        "Runs as the first call at the dossier cadence, after eager facts integration. "
        "It sees the active portrait-claim board and the new cross-stream conversation; "
        "assistant turns provide context, while every accepted change must cite user text.",
        (
            "Keep strict JSON and the canonical update, retire, and add lists.",
            "Keep the fixed English claim_type and basis enums; natural-language claim text "
            "and quotes should match the user's language.",
            "Do not weaken user-turn citations, the two-turn threshold for inferences, or "
            "the distinction between considering and deciding.",
        ),
    ),
    "memory.dossier.render": (
        "Renders one compact narrative portrait from verified portrait claims and "
        "durable facts, without reading raw assistant replies or recursively treating "
        "the previous prose dossier as evidence.",
        "Runs as the second call at the dossier cadence. Its data message contains all "
        "active portrait claims and active durable facts; a successful result replaces "
        "the prose dossier later supplied as background in chat.",
        (
            "Keep strict JSON, the canonical \"dossier\" key, language matching, and the "
            "compact narrative size limit.",
            "Use portrait claims for interpretation and facts only as durable anchors; "
            "do not derive a recurring pattern from one fact.",
            "Keep the semantic audit against cited user quotes; provenance validation "
            "alone does not prove that a claim's wording is fully supported.",
            "Preserve uncertainty and contextualize current states rather than turning "
            "them into timeless traits.",
        ),
    ),
    "memory.facts.integrate": (
        "Updates the durable-fact board from a completed conversation span. It "
        "decides whether supported user evidence should add a fact, update an "
        "existing fact, or retire something that no longer holds.",
        "Runs eagerly in the background after each completed chat turn. It sees the "
        "active board, a dated cross-stream span, and trusted user-turn labels; code "
        "validates proposed evidence again before writes.",
        (
            "Keep {date}, {board}, {span}, strict JSON, and update/retire/add schemas.",
            "Never treat assistant statements as evidence; inferred observations "
            "need support from multiple distinct user turns.",
            "Prefer updating a fact over adding a duplicate, and retain time premises.",
        ),
    ),
    "memory.facts.compact": (
        "Reduces duplication in the durable-fact board by merging overlapping facts "
        "and retiring facts that are contradicted or fully superseded, while "
        "preserving every unique piece of information.",
        "After fact integration, the facts job checks its configured cadence; when "
        "the cadence condition is met, compaction proceeds only if at least two "
        "active facts exist. It sees the board but no fresh conversation evidence.",
        (
            "Keep {board}, strict JSON, and the canonical merge and retire keys.",
            "Be conservative because this stage has no raw span from which to recover "
            "information lost by a mistaken merge or retirement.",
            "Never merge different people or topics merely due to similar wording.",
        ),
    ),
    "tool.recall_memory.description": (
        "Describes the recall_memory function to the chat model and teaches it when "
        "a targeted search of prior conversations would materially improve the "
        "current answer.",
        "Inserted into the tool schema when the registry is built for each reply. "
        "The model reads it before deciding whether to call the tool and what focused "
        "semantic query to generate.",
        (
            "This changes tool selection, not retrieval ranking or stream isolation.",
            "Encourage focused semantic queries rather than copying the raw message.",
            "A broad trigger adds latency; a narrow one hides useful past context.",
        ),
    ),
    "tool.web_search.description": (
        "Describes web_search to the chat model, including the kinds of current, "
        "fast-moving, niche, or uncertain information that should trigger a live "
        "search rather than reliance on model memory.",
        "Inserted into the tool schema for every assistant reply. The capability is "
        "advertised even without a configured provider, in which case execution "
        "returns a graceful unavailable result.",
        (
            "This does not enable a provider or change implementation and limits.",
            "Encourage focused queries and evidence cross-checking.",
            "Avoid requiring search for stable facts; needless calls add latency.",
        ),
    ),
    "llm.json_only_hint": (
        "Adds a provider-compatibility instruction to structured LLM calls so "
        "providers without reliable native JSON mode still return one parseable "
        "JSON object.",
        "Appended internally to every chat_json system prompt, including summary, "
        "dossier, facts, compaction, and trait extraction. It is code-owned, "
        "read-only, and absent from editable release items.",
        (
            "This item is intentionally not editable from the Prompt workspace.",
            "Changes require code review because malformed wording can break all "
            "structured background jobs at once.",
        ),
    ),
    "traits.mbti.extract": (
        "Extracts evidence for the four MBTI axes—E/I, S/N, T/F, and J/P—from one "
        "user-only span, then feeds that observation into the Bayesian long-term "
        "trait merge.",
        "Runs as one structured call at the trait batch cadence. $raw_entry is the "
        "new span, $profile_summary is prior context, and $rubric is the separately "
        "managed MBTI scoring guide.",
        (
            "Keep all three $ variables and canonical E_I, S_N, T_F, J_P keys.",
            "Preserve pole direction: 0 means I/S/T/J and 100 means E/N/F/P.",
            "Use null for no signal; 50 means balanced evidence, not uncertainty.",
        ),
    ),
    "traits.mbti.rubric": (
        "Defines the meaning, pole direction, score ranges, and confidence "
        "calibration used by MBTI extraction so observations remain comparable "
        "across conversation batches.",
        "Inserted verbatim into the $rubric placeholder during each MBTI extraction. "
        "It does not trigger a separate model request and is pinned with the extract "
        "template in one release snapshot.",
        (
            "Keep pole directions synchronized with extraction and UI rendering.",
            "Preserve the distinction between null, balance near 50, and low confidence.",
        ),
    ),
    "traits.ocean.extract": (
        "Extracts evidence for Openness, Conscientiousness, Extraversion, "
        "Agreeableness, and Neuroticism from one user-only span before Bayesian "
        "merging into the long-term OCEAN profile.",
        "Runs as one structured call at the trait batch cadence. It receives "
        "$raw_entry, $profile_summary, and the separately managed $rubric, all from "
        "the same pinned Prompt release.",
        (
            "Keep all three $ variables and canonical uppercase O, C, E, A, N keys.",
            "Return null when a dimension has no clear signal; most spans are sparse.",
            "Keep evidence in the user's language while JSON keys stay English.",
        ),
    ),
    "traits.ocean.rubric": (
        "Defines the five OCEAN dimensions, score bands, confidence calibration, "
        "and abstention behavior used to turn conversational evidence into stable, "
        "comparable observations.",
        "Inserted verbatim into the $rubric placeholder for every OCEAN extraction. "
        "It does not make an independent LLM call and is resolved from the same "
        "release as the extraction template.",
        (
            "Keep definitions consistent with the 0–100 unipolar display.",
            "Do not redefine null as a low or midpoint score.",
            "Coordinate score-semantic changes with extraction and interpretation.",
        ),
    ),
    "traits.regulatory_focus.extract": (
        "Extracts independent promotion-focus and prevention-focus signals from a "
        "user-only span: striving toward gains and ideals versus vigilance against "
        "losses and obligations.",
        "Runs as one structured call at the trait batch cadence with $raw_entry, "
        "$profile_summary, and $rubric, then Bayesian-merges the observation into "
        "the long-term profile.",
        (
            "Keep all three $ variables and canonical promotion/prevention keys.",
            "The dimensions are independent: either, both, or neither may signal.",
            "Use null for absent evidence rather than a low-confidence midpoint.",
        ),
    ),
    "traits.regulatory_focus.rubric": (
        "Defines promotion and prevention signals, score bands, confidence "
        "calibration, and abstention rules so regulatory-focus observations remain "
        "consistent over time.",
        "Inserted verbatim into $rubric for every regulatory-focus extraction. It "
        "does not cause a separate model request and shares the extraction call's "
        "pinned Prompt release.",
        (
            "Do not rewrite the two dimensions as opposite ends of one axis.",
            "Keep score and confidence meanings synchronized with extraction.",
        ),
    ),
    "traits.schwartz.extract": (
        "Extracts sparse evidence for the ten Schwartz basic values from a user-only "
        "conversation span and merges supported observations into the long-term "
        "values profile.",
        "Runs as one structured call at the trait batch cadence using $raw_entry, "
        "$profile_summary, and the separately managed $rubric from the same pinned "
        "Prompt release.",
        (
            "Keep all three $ variables and all ten canonical lowercase keys.",
            "Preserve sparse extraction; a typical span expresses one to three values.",
            "Use null for unsupported values and evidence in the user's language.",
        ),
    ),
    "traits.schwartz.rubric": (
        "Defines the ten Schwartz values, their behavioral signals, score ranges, "
        "confidence calibration, and sparse-abstention policy used by extraction.",
        "Inserted verbatim into the $rubric placeholder during each Schwartz "
        "extraction. It is not a separate request and is pinned with the extraction "
        "template for the whole batch.",
        (
            "Keep meanings synchronized with all ten extraction output keys.",
            "Do not broaden definitions until most values appear in every span.",
            "Do not redefine null as a neutral or average score.",
        ),
    ),
}
