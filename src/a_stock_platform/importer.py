from __future__ import annotations

import csv
import io
from typing import Any, BinaryIO


def parse_csv_rows(stream: BinaryIO | str | bytes) -> list[dict[str, Any]]:
    """Read UTF-8 CSV rows containing trade_date and close columns."""
    if isinstance(stream, bytes):
        text = stream.decode("utf-8-sig")
    else:
        text = stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "trade_date" not in reader.fieldnames or "close" not in reader.fieldnames:
        raise ValueError("CSV must have trade_date and close columns")
    rows = [
        {
            "trade_date": row["trade_date"],
            "close": row["close"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "volume": row.get("volume"),
        }
        for row in reader
    ]
    if not rows:
        raise ValueError("CSV contains no data rows")
    return rows
