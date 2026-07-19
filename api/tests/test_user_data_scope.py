from app import config
from app.data_scope import user_scope
import json

from app.store import conversation_evals, db, memory, user_states
from app.store import vectors
from app.store.vectors import VectorStore


def test_each_user_gets_an_independent_sqlite_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))

    with user_scope("user-a"):
        db.run_migrations()
        memory.append_message("user", "Alice secret")
        assert config.db_path() == tmp_path / "users" / "user-a" / "vellum.db"

    with user_scope("user-b"):
        db.run_migrations()
        memory.append_message("user", "Bob secret")
        assert [m["content"] for m in memory.recent_tail(10)] == ["Bob secret"]

    with user_scope("user-a"):
        assert [m["content"] for m in memory.recent_tail(10)] == ["Alice secret"]


def test_each_user_gets_an_independent_state_timeline(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    snapshot = {
        "states": [{
            "dimension": "emotion", "text": "Alice feels uncertain.",
            "evidence": [{"turn": 0, "quote": "uncertain"}],
        }],
        "deltas": [],
    }
    with user_scope("user-a"):
        db.run_migrations()
        user_states.record(
            user_turn=0, stream="neutral", snapshot=snapshot,
            inquiry_id=None, run_id="alice-state",
        )

    with user_scope("user-b"):
        db.run_migrations()
        assert user_states.recent() == []

    with user_scope("user-a"):
        assert user_states.recent()[0]["snapshot"] == snapshot


def test_each_user_keeps_an_independent_in_memory_vector_index(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    vectors._db_indexes.clear()

    with user_scope("user-a"):
        db.run_migrations()
        VectorStore().add(1, [1.0, 0.0])
        alice_index = VectorStore().index

    with user_scope("user-b"):
        db.run_migrations()
        VectorStore().add(2, [0.0, 1.0])
        assert VectorStore().search([1.0, 0.0], k=1) == [2]

    with user_scope("user-a"):
        assert VectorStore().index is alice_index
        assert VectorStore().search([1.0, 0.0], k=1) == [1]


def test_each_user_gets_independent_conversation_eval_archives(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))

    def create(label: str) -> dict:
        messages = [{"role": "system", "content": f"{label} SYSTEM"}]
        return conversation_evals.create_record({
            "source_user_turn": 0,
            "source_assistant_turn": 1,
            "stream": "neutral",
            "source_created_at": "2026-07-17 00:00:00",
            "source_user_content": f"{label} input",
            "baseline_output": f"{label} baseline",
            "baseline_prompt_release_id": None,
            "baseline_prompt_release_version": None,
            "baseline_prompt_label": "Original Prompt",
            "baseline_system_prompt": f"{label} BASELINE",
            "baseline_input_json": json.dumps(messages),
            "prompt_kind": "custom",
            "prompt_release_id": None,
            "prompt_release_version": None,
            "prompt_version_id": None,
            "prompt_label": label,
            "system_prompt": f"{label} SYSTEM",
            "input_json": json.dumps(messages),
            "runtime_snapshot_json": "{}",
        })

    with user_scope("user-a"):
        create("Alice")
        assert [row["prompt_label"] for row in conversation_evals.list_records()] == ["Alice"]

    with user_scope("user-b"):
        assert conversation_evals.list_records() == []
        create("Bob")

    with user_scope("user-a"):
        assert [row["prompt_label"] for row in conversation_evals.list_records()] == ["Alice"]
