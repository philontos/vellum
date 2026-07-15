from app.config import dimensions_loader as dl
from app.config.graph_rules import PROFILE_MERGE


def test_constants_present():
    for k in ("gamma", "tau_prior", "tau_ref", "min_conf"):
        assert k in PROFILE_MERGE


def test_loads_four_dimensions():
    m = dl.load_dimensions()
    assert {"ocean", "mbti", "schwartz", "regulatory_focus"} <= set(m)
    ocean = m["ocean"]
    assert ocean["_extract"]                       # template text loaded
    assert [s["key"] for s in ocean["sub_dimensions"]] == ["O", "C", "E", "A", "N"]
    assert "single entry" not in ocean["_extract"]  # reworded to span


def test_all_trait_prompts_follow_the_language_contract():
    for dimension in dl.load_dimensions().values():
        assert "Match the user's language" in dimension["_extract"]
