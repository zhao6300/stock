from a_stock_platform.models import compute_activity_score, detect_action, score_text


def test_empty_text_scores_neutral() -> None:
    result = compute_activity_score("", {"买入": 2.0})
    assert result.score == 0.0
    assert result.action == "hold"
