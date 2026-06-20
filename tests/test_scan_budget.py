"""Scan budget must not stop multi-chunk Groq scans after ~10 chunks."""

from prodguardian.llm.budget import (
    GROQ_CHUNK_THROTTLE_DEFAULT,
    GROQ_THROTTLE_PROFILES,
    GroqChunkThrottle,
    TokenBudget,
    clamp_groq_chunk_delay,
    estimate_cost,
)
from prodguardian.llm.llm_router import MAX_RATE_LIMIT_RETRIES


def test_groq_cost_estimate_is_tiny():
    assert estimate_cost(4000, "groq/llama-3.1-8b-instant") < 0.001


def test_scan_budget_allows_many_chunks_without_session_token_cap():
    budget = TokenBudget(
        max_tokens=32_000,
        max_cost_usd=0.10,
        enforce_session_token_cap=False,
    )
    for _ in range(100):
        can, reason = budget.can_proceed(3600, "groq/llama-3.1-8b-instant")
        assert can, reason
        budget.consume(3100)


def test_groq_defaults_match_recommendation():
    assert GROQ_CHUNK_THROTTLE_DEFAULT == 6
    assert MAX_RATE_LIMIT_RETRIES == 5
    assert GROQ_THROTTLE_PROFILES["balanced"] == 6


def test_clamp_groq_chunk_delay():
    assert clamp_groq_chunk_delay(1) == 3
    assert clamp_groq_chunk_delay(6) == 6
    assert clamp_groq_chunk_delay(99) == 20


def test_adaptive_groq_throttle():
    throttle = GroqChunkThrottle(6)
    throttle.record_success()
    assert throttle.delay == 5
    throttle.record_rate_limit()
    assert throttle.delay == 8
    for _ in range(10):
        throttle.record_rate_limit()
    assert throttle.delay == 20
    for _ in range(20):
        throttle.record_success()
    assert throttle.delay == 3