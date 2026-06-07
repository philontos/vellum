from app.model_loop import bayes


def test_repeated_observations_converge_upward():
    content = {}
    for _ in range(8):
        content = bayes.merge_subdims("ocean", content, {"O": {"score": 80, "confidence": 0.6}})
    assert content["O"]["score"] > 60          # tracked toward the signal
    assert "tau" in content["O"] and "confidence" in content["O"]


def test_null_keeps_old():
    content = bayes.merge_subdims("ocean", {"O": {"score": 70, "tau": 5.0}}, {"O": None})
    assert content["O"]["score"] == 70


def test_low_confidence_filtered():
    content = bayes.merge_subdims("ocean", {"O": {"score": 70, "tau": 5.0}},
                                  {"O": {"score": 10, "confidence": 0.01}})
    assert content["O"]["score"] == 70         # below min_conf → ignored
