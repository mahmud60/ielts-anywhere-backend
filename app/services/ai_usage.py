"""Record AI API usage (tokens + estimated cost) for the admin AI-usage view.

`add_usage` stages a row on the caller's existing session, so it commits inside
the same transaction as the request/task — and `.add()` is synchronous on both
async and sync SQLAlchemy sessions, so the one helper works in FastAPI routes and
Celery tasks alike. It never raises: usage logging must not break grading.
"""

import logging

logger = logging.getLogger(__name__)

# Approximate USD pricing per 1,000,000 tokens, as (input, output).
# These are estimates for the admin view — adjust to your actual contract.
_PRICING = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = _PRICING.get(model, (0.0, 0.0))
    return round(
        (input_tokens or 0) / 1_000_000 * price_in
        + (output_tokens or 0) / 1_000_000 * price_out,
        6,
    )


def anthropic_tokens(response) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from an Anthropic Messages response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def add_usage(
    session,
    *,
    module: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id=None,
    provider: str = "anthropic",
) -> None:
    """Stage an AIUsage row on `session` (committed with the caller's transaction)."""
    try:
        from app.models.ai_usage import AIUsage

        session.add(
            AIUsage(
                user_id=user_id,
                module=module,
                provider=provider,
                model=model,
                input_tokens=int(input_tokens or 0),
                output_tokens=int(output_tokens or 0),
                cost_usd=estimate_cost(model, input_tokens, output_tokens),
            )
        )
    except Exception:
        logger.warning("Failed to record AI usage (%s / %s)", module, model, exc_info=True)
