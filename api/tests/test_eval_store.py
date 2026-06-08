"""observability.db DAO: eval_runs / eval_results + eval-trace prune exemption."""
from app.store import observability as obs
from app.store import traces


def test_run_lifecycle(migrated_db):
    rid = obs.create_run("traits", total=3, model="sys-m", eval_model=None)
    run = obs.get_run(rid)
    assert run["status"] == "running" and run["suite"] == "traits"
    assert run["total"] == 3 and run["completed"] == 0
    assert run["model"] == "sys-m" and run["aggregate"] is None

    obs.bump_completed(rid)
    obs.bump_completed(rid)
    assert obs.get_run(rid)["completed"] == 2

    obs.finish_run(rid, "done", aggregate={"pass_rate": 0.67})
    done = obs.get_run(rid)
    assert done["status"] == "done"
    assert done["aggregate"] == {"pass_rate": 0.67}
    assert done["finished_at"] is not None

    assert obs.list_runs()[0]["id"] == rid          # newest first


def test_results_ordered_and_parsed(migrated_db):
    rid = obs.create_run("traits", total=2)
    obs.add_result(rid, 1, "ocean_O_high", "pass", result={"target_score": 72})
    obs.add_result(rid, 0, "ocean_C_low", "fail", result={"target_score": 55})
    rows = obs.results_for_run(rid)
    assert [r["seq"] for r in rows] == [0, 1]        # ordered by seq
    assert rows[0]["case_name"] == "ocean_C_low"
    assert rows[1]["result"] == {"target_score": 72}  # result_json parsed back


def test_error_result(migrated_db):
    rid = obs.create_run("traits", total=1)
    obs.add_result(rid, 0, "ocean_O_high", "error", error="model not configured")
    r = obs.results_for_run(rid)[0]
    assert r["status"] == "error" and r["error"] == "model not configured"
    assert r["result"] is None


def test_eval_trace_linked_and_excluded_from_chat_list(migrated_db):
    rid = obs.create_run("traits", total=1)
    traces.record(turn=None, stage="trait", model="m", params={}, prompt="p",
                  output="o", prompt_tokens=1, completion_tokens=1, duration_ms=1,
                  eval_run_id=rid, eval_case="ocean_O_high")
    traces.record(turn=1, stage="chat", model="m", params={}, prompt="cp",
                  output="co", prompt_tokens=1, completion_tokens=1, duration_ms=1)

    eval_traces = obs.traces_for_run(rid)
    assert len(eval_traces) == 1 and eval_traces[0]["eval_case"] == "ocean_O_high"

    chat = traces.list_recent(limit=10)              # chat list excludes eval traces
    assert len(chat) == 1 and chat[0]["stage"] == "chat"


def test_prune_spares_eval_traces(migrated_db):
    rid = obs.create_run("traits", total=1)
    traces.record(turn=None, stage="trait", model="m", params={}, prompt="EVAL_P",
                  output="EVAL_O", prompt_tokens=1, completion_tokens=1, duration_ms=1,
                  eval_run_id=rid, eval_case="ocean_O_high")
    traces.record(turn=1, stage="chat", model="m", params={}, prompt="CHAT_P",
                  output="CHAT_O", prompt_tokens=1, completion_tokens=1, duration_ms=1)

    traces.prune(keep_last=0)                         # prune everything eligible

    eval_t = obs.traces_for_run(rid)[0]
    assert eval_t["prompt"] == "EVAL_P" and eval_t["output"] == "EVAL_O"  # exempt
    chat_t = traces.list_recent(limit=10)[0]
    assert chat_t["prompt"] is None and chat_t["output"] is None          # pruned
