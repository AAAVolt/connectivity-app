"""Diminishing returns transform for accessibility scoring."""


def concave_transform(raw_score: float, beta: float) -> float:
    """Apply concave (diminishing returns) transform: score ^ beta.

    With 0 < beta < 1 this compresses high scores, giving
    diminishing marginal returns for additional destinations.

    Args:
        raw_score: Non-negative raw accessibility score.
        beta: Concavity exponent, must be in (0, 1).

    Raises:
        ValueError: If raw_score < 0 or beta not in (0, 1).
    """
    if raw_score < 0:
        raise ValueError(f"raw_score must be >= 0, got {raw_score}")
    if beta <= 0 or beta >= 1:
        raise ValueError(f"beta must be in (0, 1), got {beta}")
    if raw_score == 0:
        return 0.0
    return raw_score ** beta
