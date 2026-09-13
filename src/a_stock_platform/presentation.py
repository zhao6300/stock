from __future__ import annotations

from typing import Iterable


def sparkline(candles: list[dict[str, object]], width: int = 240, height: int = 60) -> str:
    """Return a compact SVG sparkline for a price series."""
    closes = [float(row["close"]) for row in candles]
    if len(closes) < 2:
        return ""
    high = max(closes)
    low = min(closes)
    span = high - low
    points = []
    for index, close in enumerate(closes):
        x = (index / (len(closes) - 1)) * width
        y = height - ((close - low) / span) * height
        points.append(f"{x:.1f},{y:.1f}")
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="价格走势"><polyline fill="none" stroke="#2b6cff" stroke-width="2" points="{" ".join(points)}" /></svg>'
