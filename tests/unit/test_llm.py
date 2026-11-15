from langchain_core.runnables import RunnableWithFallbacks

from agent.llm import chat_model


def test_only_cheap_nodes_get_a_fallback_model(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("MODEL_PROFILE", "open")
    assert isinstance(chat_model("analyst"), RunnableWithFallbacks)
    assert not isinstance(chat_model("writer"), RunnableWithFallbacks)
    assert not isinstance(chat_model("analyst", model="x"), RunnableWithFallbacks)
