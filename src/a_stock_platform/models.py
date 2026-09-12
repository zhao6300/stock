from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityScore:
    score: float
    action: str
    matched_terms: tuple[str, ...]


def score_text(text: str, vocabulary: dict[str, float]) -> float:
    return 0.0


def detect_action(score: float) -> str:
    return "hold"


def compute_activity_score(text: str, vocabulary: dict[str, float]) -> ActivityScore:
    return ActivityScore(0.0, "hold", ())
