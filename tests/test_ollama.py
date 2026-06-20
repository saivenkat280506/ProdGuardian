import json
from unittest.mock import MagicMock, patch

from prodguardian.llm.ollama import (
    RECOMMENDED_SMALL_MODELS,
    _list_via_api,
    build_ollama_select_options,
    is_model_installed,
    list_ollama_models,
    ollama_litellm_model,
)


class TestOllamaHelpers:
    def test_ollama_litellm_model_prefix(self):
        assert ollama_litellm_model("llama3.2:latest") == "ollama/llama3.2:latest"
        assert ollama_litellm_model("ollama/mistral:latest") == "ollama/mistral:latest"

    def test_is_model_installed_exact_and_base_match(self):
        installed = ["llama3.2:latest", "mistral:latest"]
        assert is_model_installed("llama3.2:latest", installed)
        assert is_model_installed("llama3.2:1b", installed) is False
        assert is_model_installed("gemma2:2b", installed) is False

    def test_build_ollama_select_options_marks_installed_and_downloads(self):
        installed = ["llama3.2:latest"]
        options = build_ollama_select_options(installed, RECOMMENDED_SMALL_MODELS)

        assert any(value == "llama3.2:latest" and "[installed]" in display for display, value in options)
        assert any(value == "llama3.2:1b" and "download" in display for display, value in options)
        assert not any(value == "llama3.2:1b" and "[installed]" in display for display, value in options)

    @patch("urllib.request.urlopen")
    def test_list_via_api_parses_models(self, mock_urlopen):
        payload = {
            "models": [
                {"name": "llama3.2:latest"},
                {"name": "mistral:latest"},
            ]
        }
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        mock_urlopen.return_value = response

        models, error = _list_via_api("http://localhost:11434", 5.0)

        assert error is None
        assert models == ["llama3.2:latest", "mistral:latest"]

    @patch("prodguardian.llm.ollama._list_via_cli", return_value=([], "cli failed"))
    @patch("prodguardian.llm.ollama._list_via_api", return_value=([], "not running"))
    def test_list_ollama_models_returns_error_when_unavailable(self, _mock_api, _mock_cli):
        models, error = list_ollama_models()
        assert models == []
        assert error == "not running"