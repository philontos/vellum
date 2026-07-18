DIMENSION = {
    "key":             "schwartz",
    "name":            "Schwartz Basic Values",
    "enabled":         True,
    "prompt_template": "extract.spt",
    "summary_format":  "relative_priorities",
    "summary_label":   "Values",
    "sort_by_score":   False,          # fixed motivational-circle order
    "visualization":   "circumplex",
    "sub_dimensions": [
        {"key": "self_direction", "name": "Self-Direction"},
        {"key": "stimulation",    "name": "Stimulation"},
        {"key": "hedonism",       "name": "Hedonism"},
        {"key": "achievement",    "name": "Achievement"},
        {"key": "power",          "name": "Power"},
        {"key": "security",       "name": "Security"},
        {"key": "conformity",     "name": "Conformity"},
        {"key": "tradition",      "name": "Tradition"},
        {"key": "benevolence",    "name": "Benevolence"},
        {"key": "universalism",   "name": "Universalism"},
    ],
    # V2 is a signed within-person index, not a normative percentile.
    "score_range": [-1, 1],
}
