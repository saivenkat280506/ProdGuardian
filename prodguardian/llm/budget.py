from typing import Optional

# Per-request input caps (prompt tokens). Groq free tier is 6000 TPM — leave headroom.
DEFAULT_MODEL_INPUT_LIMIT = 24_000
MODEL_INPUT_TOKEN_LIMITS: dict[str, int] = {
    "groq/llama-3.1-8b-instant": 3_800,
    "groq/llama-3.3-70b-versatile": 4_200,
    "groq/": 3_800,
}

DEFAULT_MODEL_OUTPUT_TOKENS = 1_200
MODEL_OUTPUT_TOKEN_LIMITS: dict[str, int] = {
    "groq/llama-3.1-8b-instant": 500,
    "groq/llama-3.3-70b-versatile": 700,
    "groq/": 500,
}

TOKEN_SAFETY_MARGIN = 200

# Groq free tier is ~6000 TPM; pause between chunk requests to avoid rate limits.
GROQ_CHUNK_THROTTLE_DEFAULT = 6
GROQ_CHUNK_THROTTLE_MIN = 3
GROQ_CHUNK_THROTTLE_MAX = 20
GROQ_ADAPTIVE_FLOOR = 3
GROQ_ADAPTIVE_RATE_LIMIT_STEP = 3
GROQ_ADAPTIVE_SUCCESS_STEP = 1

# Backward-compatible alias for code that imported the old constant name.
GROQ_CHUNK_THROTTLE_SECONDS = GROQ_CHUNK_THROTTLE_DEFAULT

GROQ_THROTTLE_PROFILES: dict[str, int] = {
    "fast": 3,
    "balanced": 6,
    "safe": 12,
}


def clamp_groq_chunk_delay(seconds: float | int) -> int:
    """Clamp user-configured Groq inter-chunk delay to the supported range."""
    return int(
        max(
            GROQ_CHUNK_THROTTLE_MIN,
            min(GROQ_CHUNK_THROTTLE_MAX, round(float(seconds))),
        )
    )


class GroqChunkThrottle:
    """
    Adaptive pause between Groq scan chunks.

    Speeds up when requests succeed; backs off after 429/rate-limit retries.
    """

    def __init__(self, initial_delay: int = GROQ_CHUNK_THROTTLE_DEFAULT):
        self.delay = clamp_groq_chunk_delay(initial_delay)

    def wait_before_next_chunk(self) -> float:
        """Sleep for the current delay and return seconds waited."""
        import time

        time.sleep(self.delay)
        return float(self.delay)

    def record_rate_limit(self) -> None:
        self.delay = min(
            GROQ_CHUNK_THROTTLE_MAX,
            self.delay + GROQ_ADAPTIVE_RATE_LIMIT_STEP,
        )

    def record_success(self) -> None:
        self.delay = max(GROQ_ADAPTIVE_FLOOR, self.delay - GROQ_ADAPTIVE_SUCCESS_STEP)


def _match_model_limit(model: str, table: dict[str, int], default: int) -> int:
    normalized = model.strip().lower()
    best_prefix = ""
    best_limit = default
    for prefix, limit in table.items():
        key = prefix.lower()
        if normalized.startswith(key) and len(key) > len(best_prefix):
            best_prefix = key
            best_limit = limit
    return best_limit


def model_input_token_limit(model: str) -> int:
    """Max prompt tokens for a single API request on this model."""
    return _match_model_limit(model, MODEL_INPUT_TOKEN_LIMITS, DEFAULT_MODEL_INPUT_LIMIT)


def model_output_token_limit(model: str) -> int:
    """Suggested max output tokens for scan responses on this model."""
    return _match_model_limit(model, MODEL_OUTPUT_TOKEN_LIMITS, DEFAULT_MODEL_OUTPUT_TOKENS)


def model_needs_compact_guardrails(model: str) -> bool:
    """Small-context / rate-limited models use a shorter presets block."""
    return model_input_token_limit(model) <= 5_500


def model_needs_chunk_throttle(model: str) -> bool:
    """Providers with tight TPM limits need a pause between chunk requests."""
    return model.strip().lower().startswith("groq/")


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens using tiktoken."""
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4


def estimate_cost(tokens: int, model: str) -> float:
    """Estimate USD cost. Approximate rates as of 2026."""
    normalized = model.strip().lower()
    if normalized.startswith("ollama/"):
        return 0.0
    if normalized.startswith("groq/"):
        return (tokens / 1_000_000) * 0.05

    rates = {
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "gpt-4o": (0.0025, 0.01),
        "claude-3-haiku": (0.00025, 0.00125),
        "claude-3-sonnet": (0.003, 0.015),
    }
    for key, (in_rate, out_rate) in rates.items():
        if normalized.startswith(key):
            return (tokens / 1000) * out_rate
    return 0.01


class TokenBudget:
    def __init__(
        self,
        max_tokens: Optional[int] = 32000,
        max_cost_usd: Optional[float] = 0.10,
        *,
        enforce_session_token_cap: bool = True,
    ):
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.enforce_session_token_cap = enforce_session_token_cap
        self.used_tokens = 0
        self.used_cost = 0.0

    def estimate_call_cost(
        self, prompt_tokens: int, max_output_tokens: int, model: str
    ) -> float:
        return estimate_cost(prompt_tokens + max_output_tokens, model)

    def can_proceed(
        self, additional_tokens: int, model: str
    ) -> tuple[bool, str]:
        est_cost = self.estimate_call_cost(additional_tokens, 500, model)
        if self.max_cost_usd is not None and (self.used_cost + est_cost) > self.max_cost_usd:
            return (
                False,
                f"Estimated cost ${est_cost:.4f} would exceed budget of ${self.max_cost_usd:.2f}",
            )
        if (
            self.enforce_session_token_cap
            and self.max_tokens is not None
            and self.max_tokens > 0
            and self.used_tokens + additional_tokens > self.max_tokens
        ):
            return False, f"Token limit ({self.max_tokens}) exceeded"
        return True, "OK"

    def consume(self, tokens: int, cost: float = 0.0):
        self.used_tokens += tokens
        self.used_cost += cost

    def remaining_budget(self) -> float:
        if self.max_cost_usd is None:
            return float("inf")
        return max(0, self.max_cost_usd - self.used_cost)
