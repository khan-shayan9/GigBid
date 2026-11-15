"""Scoring rules of the R&D A runner."""

from evals.runners.rnd_a_tool_granularity import first_call, matches, score, with_defaults


def test_argument_matching_rules() -> None:
    assert matches("~rag", "RAG chatbots") and not matches("~rag", "vision")
    assert matches(["python"], ["Python", "FastAPI"]) and not matches(["python"], "python")
    assert matches(5, "5") and matches(600, 600.0) and not matches(True, "true")
    assert matches("2026-11-14T00:00:00Z", "2026-11-14T05:00:00+05:00")
    assert matches({"types": ["case_study"]}, {"types": ["case_study"], "outcomes": []})


def test_defaults_count_and_coarse_calls_unwrap() -> None:
    schema = {"properties": {"dry_run": {"default": True}, "k": {"default": 5}}}
    assert with_defaults({"k": 3}, schema) == {"dry_run": True, "k": 3}
    call = [{"name": "workspace", "args": {"action": "hold_slot", "arguments": {"x": 1}}}]
    assert first_call("coarse", call) == ("hold_slot", {"x": 1})
    task = {"task_id": "a01", "node": "writer", "expected_tool": "hold_slot",
            "expected_args": {"dry_run": True}}
    raw = {"tool_calls": call, "input_tokens": 10, "output_tokens": 2, "seconds": 1.0}
    row = score("coarse", task, raw, {"hold_slot": schema})
    assert row["tool_ok"] and row["args_ok"] and row["tokens"] == 12
