def compute_metrics(candles: list[dict[str, float | str]]) -> dict[str, float | int | str]:
    closes = [float(row["close"]) for row in candles]
    if not closes:
        raise ValueError("At least one close price is required")
    return {"count": len(closes), "latest": closes[-1]}
