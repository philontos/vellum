# Schwartz Basic Values Scoring Guide

**Achievement**: Drive for personal success, demonstrating competence, and social recognition. Signals: focus on outcomes, competitive mindset, self-evaluation against standards.
**Power**: Desire for control over resources, status, and others. Signals: pursuit of influence, hierarchy-consciousness, valuing authority.
**Hedonism**: Seeking pleasure and sensory gratification. Signals: emphasis on comfort, entertainment, present-moment enjoyment.
**Stimulation**: Craving novelty, challenge, and excitement. Signals: welcoming change, boredom with routine, actively seeking new experiences.
**Self-Direction**: Freedom to think and act independently. Signals: insistence on autonomy, creativity, resistance to external constraint.
**Universalism**: Understanding and concern for all people and nature. Signals: focus on fairness and justice, environmental awareness, openness to diverse cultures.
**Benevolence**: Care and support for people in one's immediate circle. Signals: loyalty, altruism, dedication to family and close friends.
**Tradition**: Respect for and preservation of cultural customs and heritage. Signals: valuing historical continuity, following conventions, religious observance.
**Conformity**: Compliance with social norms to avoid harming others. Signals: rule-following, politeness, self-restraint.
**Security**: Need for stability, harmony, and safety. Signals: risk avoidance, desire for order, preference for certainty.

# Evidence strength (not a person-level score)

| Basis | What counts |
|-------|-------------|
| `costly_choice` | The user paid a real cost or accepted risk to uphold the value |
| `tradeoff` | The user explicitly chose this value over another |
| `repeated_behavior` | The same priority appears in distinct situations in this span |
| `self_statement` | The user directly says the value matters or does not matter |
| `aspiration` | The user wants to embody it but has not shown a choice yet |
| `emotion` | The value is salient now; update activation only, not durable priority |

`strength` describes how decisively this episode expresses the direction. It is
not an absolute importance score and is never centered at 0.5.

# Confidence calibration

| Confidence | When to use |
|------------|-------------|
| 0.85–1.0 | Direct statement or strong behavioral signal |
| 0.6–0.85 | Indirect signal, reasonable inference |
| 0.4–0.6  | Weak signal |
| 0.2–0.4  | Tentative — consider whether `null` is more honest |
| < 0.2    | Prefer `null` over a low-confidence score |

**`null` means "no priority evidence in this span" — the canonical way to abstain.** Schwartz values are sparse — typical spans express 1–3 of the 10 values, so 7–9 should be `null`. Low relative priority is learned through repeated trade-offs or explicit rejection, never inferred from silence.
