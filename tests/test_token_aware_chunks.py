from pathlib import Path

from prodguardian.llm.budget import count_tokens, model_input_token_limit, model_output_token_limit
from prodguardian.llm.codebase_scanner import (
    build_codebase_scan_prompt,
    build_token_aware_chunks,
    scan_prompt_overhead_tokens,
)
from prodguardian.tui.settings_store import get_presets, get_rules


def test_groq_model_has_low_input_limit():
    assert model_input_token_limit("groq/llama-3.1-8b-instant") <= 4_500
    assert model_output_token_limit("groq/llama-3.1-8b-instant") <= 600


def test_token_aware_chunks_fit_groq_limit(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    for idx in range(8):
        (project / f"module_{idx}.py").write_text(
            f'API_KEY_{idx} = "sk-secret-{idx}"\n' + ("print('debug')\n" * 80)
        )

    files = sorted(project.glob("*.py"))
    presets = get_presets()
    rules = get_rules()
    model = "groq/llama-3.1-8b-instant"
    chunks, compact = build_token_aware_chunks(
        project,
        files,
        presets=presets,
        rules=rules,
        project_name="app",
        budget_model=model,
    )

    assert len(chunks) >= 2
    limit = model_input_token_limit(model)
    output_tokens = model_output_token_limit(model)

    for chunk in chunks:
        prompt = build_codebase_scan_prompt(
            chunk,
            presets,
            rules,
            "app",
            compact_guardrails=compact,
        )
        total = count_tokens(prompt, model) + output_tokens
        assert total <= limit, f"chunk exceeded limit: {total} > {limit}"


def test_scan_prompt_overhead_uses_compact_when_needed():
    presets = get_presets()
    rules = get_rules()
    model = "groq/llama-3.1-8b-instant"
    full = scan_prompt_overhead_tokens(presets, rules, "demo", model, compact_guardrails=False)
    compact = scan_prompt_overhead_tokens(presets, rules, "demo", model, compact_guardrails=True)
    assert compact < full