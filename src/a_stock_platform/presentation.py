from __future__ import annotations

from typing import Iterable


def sparkline(
    candles: list[dict[str, object]],
    width: int = 240,
    height: int = 60,
    inset: int = 6,
) -> str:
    """Return a compact SVG sparkline for a price series."""
    closes = [float(row["close"]) for row in candles]
    if len(closes) < 2:
        return ""
    high = max(closes)
    low = min(closes)
    span = high - low
    points = []
    for index, close in enumerate(closes):
        x = inset + (index / (len(closes) - 1)) * (width - inset * 2)
        y = height - inset - ((close - low) / span) * (height - inset * 2)
        points.append(f"{x:.1f},{y:.1f}")
    trend = "positive" if closes[-1] >= closes[0] else "negative"
    return (
        f'<svg class="sparkline {trend}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="价格走势"><polyline fill="none" stroke="currentColor" '
        f'stroke-width="2" points="{" ".join(points)}" /></svg>'
    )
