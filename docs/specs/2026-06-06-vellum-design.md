# Vellum Design

## Consultation contract

Vellum should feel like a curious, evidence-grounded consultant and long-term
conversation partner. The user should do most of the talking while important
personal information is missing. The assistant reflects briefly, asks one
high-information question at a time, and gives an honest judgment only after the
strength of user-authored evidence matches the strength of the proposed answer.

The user's current words and corrections are the primary source of truth. Earlier
assistant prose is continuity, not evidence. Remembered state and personality are
dated, low-authority hypotheses that the current user turn may revise or overturn.

## User-model layers

| Layer | Meaning | Lifetime | Write trigger | Answer authority |
| --- | --- | --- | --- | --- |
| Current user turn | What the user says now | One turn | Chat ingest | Highest |
| User-state snapshot | Present emotion, belief, intention, need, constraint, situation, and explicit change | Append-only timeline | Every validated Controller turn with a state signal | High, but time-sensitive |
| Inquiry Ledger | Evidence gathered for one bounded question/episode | Open until paused or closed | Controller decision validated by code | High for that Inquiry |
| Durable facts | Stable anchors and time-bounded events useful later | Until corrected or superseded | Eager background integration | Medium |
| Personality evidence and traits | Stable self-statements, repeated patterns, and relative value priorities | Slowly accumulated | Batched only outside active Inquiry | Low-authority hypothesis |
| Dossier | Compact durable portrait rendered from grounded claims and facts | Periodically replaced | Batched only outside active Inquiry | Low-authority background |
| Recall summaries | Search handles for earlier conversations | Long-lived, stream-scoped | Batched background summary | Routing/background only |

Temporary state never becomes a durable fact, portrait claim, or generic trait
observation merely because it appeared once. Dossier claims are limited to values,
patterns, decision style, and self-concept. Generic OCEAN, MBTI, and regulatory-focus
observations require a `stable_self_statement` or `repeated_pattern` basis.

## Main turn loop

1. Persist the user turn.
2. Build bounded Controller context:
   - the current user turn;
   - a user-only recent tail;
   - at most two clipped assistant messages for conversational continuity;
   - the active Inquiry Ledger and its cited user turns;
   - closed episode and prior state checkpoints marked stale until reconfirmed.
3. The Inquiry Controller returns one structured decision:
   - `direct`: the request is answerable without material user-specific discovery;
   - `inquire`: update/open/resume a Ledger and return one focused question;
   - `synthesize`: produce an answer plan after readiness validation.
4. Code validates JSON shape, exact user evidence, revision lock, transition,
   question budget, and consultation readiness. One structured repair call is
   allowed. Repeated failure degrades to a cautious direct response without
   mutating Inquiry state.
5. Persist the validated state snapshot synchronously.
6. For `inquire`, return the Controller's short question directly. For `direct` or
   `synthesize`, invoke the Chat Responder. Synthesis uses a user-only grounded tail,
   the validated Ledger, durable facts, and low-authority traits; it excludes earlier
   assistant narratives, dossier prose, and semantic recall from the factual basis.
7. Persist the assistant turn, then finalize a deferred Inquiry close. Background
   modeling runs afterward.

## Inquiry and episode lifecycle

An Inquiry is one bounded investigation. It is the operational episode boundary
for a user question, not a single message round.

`exploring -> reviewing -> closed`

An Inquiry may also become `paused`, then later `resume`. Closed Ledgers are
immutable checkpoints. Returning to the same topic opens a new Inquiry with an
explicit `related_episode_id`; unrelated topics are never linked automatically.
When a prior topic returns, earlier state is stale and the Controller asks what
changed unless the current user turn already states the delta.

The Ledger contains:

- an evidence-cited immediate goal;
- a consultation frame (`personal|practical`, answer scope, state-delta need,
  optional related episode);
- the latest current state per dimension and a state-delta history;
- typed observations, user interpretations, competing hypotheses;
- typed blocking unknowns and asked-question history;
- an optional provisional conclusion.

## Readiness gate

The Controller proposes semantic structure; deterministic code decides whether the
proposed synthesis is allowed.

| Proposed answer | Required user-grounded coverage |
| --- | --- |
| Practical/direct | No material user-specific unknown |
| Personal bounded guidance | Current state plus a material event, pattern, feedback, outcome, comparison, constraint, or preference |
| State-change claim | An explicit delta relative to the episode, a previous episode, or an unspecified past |
| Causal judgment | A concrete experience plus at least two plausible hypotheses |
| Consequential decision | A concrete experience plus user criteria, constraints, preferences, comparisons, or outcomes |

Unresolved blockers prevent non-provisional synthesis and closure. Provisional
synthesis is not a general escape hatch. It requires exactly one auditable basis:

- the user explicitly requested a provisional answer, cited from a user turn;
- the user explicitly cannot add evidence, cited from a user turn; or
- the configured question budget is actually exhausted.

A provisional answer cannot close an Inquiry.

## Context and authority policy

Context is selected by role, not only recency. User messages are evidence.
Assistant messages are clipped continuity. Closed episodes and prior state are
stale checkpoints. Dossier, facts, traits, and recall cannot fill a missing present
state or prove another person's motive, an external causal claim, or a current
market condition.

Responder modes are:

- `minimal`: current self-contained request;
- `recent`: bounded nearby exchange;
- `personal`: durable user model and focused recall when materially useful;
- `grounded`: synthesis-only, user messages plus the validated Ledger, facts, and
  low-authority traits, with assistant history excluded.

## Modeling cadence

- State snapshots: synchronous on every validated turn with a grounded signal.
- Facts: eager after every completed turn, but only durable/time-bounded content.
- Traits: every configured `K` turns per dimension, deferred while an Inquiry is
  exploring or reviewing; dimensions have independent retryable cursors.
- Dossier: every configured `M` turns, also deferred during active Inquiry. Legacy
  `current_state` portrait claims are superseded rather than rendered.
- Recall summary: every configured `S` stream turns.

All text remains in account-scoped SQLite. The vector index contains embeddings and
integer labels only. Migrations are forward-only and idempotent.

## Observability and evaluation

Admin exposes current-state snapshots, durable portrait evidence, facts, traits,
Inquiry frame/state/deltas/typed blockers, revision history, Controller/Responder
spans, selected context mode, dropped-context counts, and synthesis basis.

Inquiry evaluation reports routing accuracy, evidence validity, one-question rate,
readiness validity, state-capture rate, synthesis-basis validity, concrete-question
rate, premature-answer rate, unnecessary-Inquiry rate, lock validity, and context
mode accuracy. The regression case for declining company confidence must continue
Inquiry after the broad answer “mainly disappointment with the current company”
until the user supplies a concrete change or explicitly invokes a valid provisional
basis.
