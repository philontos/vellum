"""Eval panel routes: SSE run (relay + persist), list/detail, and a real
subprocess run with the model unconfigured (the framework-runs-now acceptance)."""
import json

from fastapi.testclient import TestClient


def _fake_lines(*frames):
    async def gen(suite):
        for f in frames:
            yield json.dumps(f)
    return gen


def test_run_relays_and_persists(migrated_db, monkeypatch):
    from app.routes import inspect
    frames = [
        {"type": "run", "suite": "traits", "total": 2, "needs_eval_gen": False},
        {"type": "trace", "case": "ocean_O_high", "stage": "trait", "model": "m",
         "prompt": "P", "output": "O", "prompt_tokens": 1, "completion_tokens": 2,
         "duration_ms": 3, "params": {"status": "ok"}},
        {"type": "case", "seq": 0, "case": "ocean_O_high", "status": "pass",
         "result": {"target_score": 72}},
        {"type": "case", "seq": 1, "case": "ocean_C_low", "status": "fail",
         "result": {"target_score": 55}},
        {"type": "done", "status": "done", "aggregate": {"pass": 1, "total": 2}},
    ]
    monkeypatch.setattr(inspect, "_stream_lines", _fake_lines(*frames))

    from app.main import app
    c = TestClient(app)
    with c.stream("POST", "/inspect/evals/run?suite=traits") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert '"run"' in body and '"case"' in body and "[DONE]" in body

    runs = c.get("/inspect/evals").json()["runs"]
    assert len(runs) == 1 and runs[0]["suite"] == "traits" and runs[0]["status"] == "done"
    rid = runs[0]["id"]

    detail = c.get(f"/inspect/evals/{rid}").json()
    assert detail["run"]["total"] == 2
    assert detail["run"]["aggregate"] == {"pass": 1, "total": 2}
    assert [r["case_name"] for r in detail["results"]] == ["ocean_O_high", "ocean_C_low"]
    assert detail["results"][0]["result"] == {"target_score": 72}
    # eval trace persisted, linked, and excluded from the chat trace list
    assert len(detail["traces"]) == 1 and detail["traces"][0]["eval_case"] == "ocean_O_high"
    assert c.get("/inspect/traces").json()["traces"] == []


def test_list_exposes_suite_catalog(migrated_db):
    from app.main import app
    c = TestClient(app)
    body = c.get("/inspect/evals").json()
    keys = {s["key"] for s in body["suites"]}
    assert keys == {"traits", "facts", "recall", "altitude", "consultant"}
    by_key = {s["key"]: s["needs_eval_gen"] for s in body["suites"]}
    assert by_key["consultant"] is True and by_key["traits"] is False


def test_run_unknown_suite_422(migrated_db):
    from app.main import app
    c = TestClient(app)
    r = c.post("/inspect/evals/run?suite=nope")
    assert r.status_code == 422


def test_run_subprocess_unconfigured_model_persists_error(migrated_db, monkeypatch):
    """Real subprocess, no model configured → every case errors, run lands as error,
    and is durably visible. Proves the framework runs end-to-end before model setup."""
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)

    from app.main import app
    c = TestClient(app)
    with c.stream("POST", "/inspect/evals/run?suite=traits") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "[DONE]" in body

    runs = c.get("/inspect/evals").json()["runs"]
    assert len(runs) == 1
    detail = c.get(f"/inspect/evals/{runs[0]['id']}").json()
    assert detail["results"], "subprocess should have produced at least one case"
    assert all(r["status"] == "error" for r in detail["results"])
    assert detail["run"]["status"] == "error"
