from fastapi.testclient import TestClient

from app.inquiry import store
from app.main import app
from app.store import turn_runs


def _ledger():
    return {
        "goal": {"text": "Decide whether to resign", "evidence": []},
        "observations": [], "interpretations": [], "hypotheses": [],
        "blocking_unknowns": [{
            "id": "u1", "question": "What happened?", "why_material": "material",
            "status": "open", "resolved_after_turn": None,
        }],
        "asked_questions": [], "provisional_conclusion": None,
    }


def test_inspect_lists_inquiries_and_revision_history(migrated_db):
    opened = store.open_inquiry(
        stream="neutral", opened_turn=2, ledger=_ledger(),
        decision={"route": "inquire"}, run_id="run-1",
    )
    client = TestClient(app)

    listed = client.get("/inspect/inquiries").json()["inquiries"]
    assert listed[0]["id"] == opened["id"]
    assert listed[0]["ledger"]["blocking_unknowns"][0]["id"] == "u1"

    detail = client.get(f"/inspect/inquiries/{opened['id']}").json()
    assert detail["inquiry"]["goal"] == "Decide whether to resign"
    assert detail["events"][0]["revision_after"] == 1
    assert client.get("/inspect/inquiries/999999").status_code == 404


def test_inspect_lists_pipeline_turn_runs(migrated_db):
    turn_runs.start(
        run_id="run-visible", user_turn=4, stream="neutral", context_meta={},
        prompt_release_id=None, prompt_release_version=None,
    )
    turn_runs.finish(
        run_id="run-visible", assistant_turn=5, route="direct", status="done",
        inquiry_id=None, revision_before=None, revision_after=None,
        controller_model="glm", responder_model="deepseek",
        decision={"route": "direct"}, error=None,
    )

    response = TestClient(app).get("/inspect/turn-runs")

    assert response.status_code == 200
    assert response.json()["runs"][0]["id"] == "run-visible"
