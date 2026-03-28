"""Tests for LocalLlamaCppService GPU offload handling."""

from src.infrastructure.llm.local_llama_cpp_service import LocalLlamaCppService


def test_init_preserves_full_gpu_offload_sentinel(monkeypatch, tmp_path):
    model_path = tmp_path / "models" / "llm" / "Qwen3-0.6B-Q8_0.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"gguf")

    monkeypatch.setattr(
        LocalLlamaCppService,
        "_resolve_model_path",
        staticmethod(lambda _model_path: model_path),
    )

    service = LocalLlamaCppService(str(model_path), n_gpu_layers=-1)

    assert service.n_gpu_layers == -1


def test_get_model_passes_negative_one_gpu_layers_to_llama(monkeypatch, tmp_path):
    model_path = tmp_path / "models" / "llm" / "Qwen3-0.6B-Q8_0.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"gguf")

    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        LocalLlamaCppService,
        "_resolve_model_path",
        staticmethod(lambda _model_path: model_path),
    )
    monkeypatch.setattr("llama_cpp.Llama", FakeLlama)

    service = LocalLlamaCppService(str(model_path), n_gpu_layers=-1)
    service._get_model()

    assert captured["n_gpu_layers"] == -1


def test_filter_thinking_tokens_removes_complete_block():
    chunks = ["hello ", "<think>hidden</think>", "world"]

    result = "".join(LocalLlamaCppService._filter_thinking_tokens(chunks))

    assert result == "hello world"


def test_filter_thinking_tokens_removes_streamed_partial_block():
    chunks = ["before<th", "ink>hidden", " text</thi", "nk>after"]

    result = "".join(LocalLlamaCppService._filter_thinking_tokens(chunks))

    assert result == "beforeafter"


def test_stream_messages_passes_tools_to_chat_completion(monkeypatch, tmp_path):
    model_path = tmp_path / "models" / "llm" / "Qwen3-0.6B-Q8_0.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"gguf")

    captured = {}

    class FakeModel:
        def create_chat_completion(self, **kwargs):
            captured.update(kwargs)
            return iter(
                [
                    {"choices": [{"delta": {"content": "<tool_call>{}</tool_call>"}}]},
                ]
            )

    monkeypatch.setattr(
        LocalLlamaCppService,
        "_resolve_model_path",
        staticmethod(lambda _model_path: model_path),
    )
    monkeypatch.setattr(LocalLlamaCppService, "_get_model", lambda self: FakeModel())

    service = LocalLlamaCppService(str(model_path), n_gpu_layers=-1)
    list(
        service.stream_messages(
            [{"role": "user", "content": "2+3"}],
            tools=[
                {
                    "type": "function",
                    "function": {"name": "calculator", "parameters": {"type": "object"}},
                }
            ],
            tool_choice="auto",
        )
    )

    assert captured["tools"][0]["function"]["name"] == "calculator"
    assert captured["tool_choice"] == "auto"
