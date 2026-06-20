"""Dimension display metadata — the names + pole labels the profile page needs to
render trait cards (bipolar diverging bars vs unipolar bars). It lives in the
dimension configs; dimension_meta() exposes a frontend-friendly slice of it."""
from app.config.dimensions_loader import dimension_meta


def test_mbti_subdimensions_are_bipolar_with_poles():
    m = dimension_meta("mbti")
    assert m["name"]                      # a human-readable dimension name
    assert m["sort_by_score"] is False    # keep canonical axis order
    e_i = next(s for s in m["sub_dimensions"] if s["key"] == "E_I")
    assert e_i["poles"] == ["I", "E"]     # 0 = I, 100 = E
    t_f = next(s for s in m["sub_dimensions"] if s["key"] == "T_F")
    assert t_f["poles"] == ["T", "F"]


def test_ocean_subdimensions_are_unipolar():
    m = dimension_meta("ocean")
    assert [s["key"] for s in m["sub_dimensions"]] == ["O", "C", "E", "A", "N"]
    o = next(s for s in m["sub_dimensions"] if s["key"] == "O")
    assert "poles" not in o               # unipolar → no poles → linear bar


def test_schwartz_sorts_by_score():
    m = dimension_meta("schwartz")
    assert m["sort_by_score"] is True


def test_unknown_dimension_is_none():
    assert dimension_meta("does-not-exist") is None
