from agent import tracing


def test_tracing_is_off_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing.callbacks("acct:bid:job-1") == []
    tracing.flush()  # a no-op, never an error


def test_every_segment_of_a_thread_shares_one_trace_id() -> None:
    first = tracing.trace_id_for("acct:bid:job-1")
    assert first == tracing.trace_id_for("acct:bid:job-1")
    assert first != tracing.trace_id_for("acct:bid:job-2") and len(first) == 32


def test_pii_is_masked_before_it_leaves() -> None:
    data = {"input": ["Mail me at jo@example.com", ("see https://evil.example",)], "n": 3}
    masked = tracing._mask(data=data)
    assert masked == {"input": ["Mail me at [EMAIL]", ["see [URL]"]], "n": 3}
