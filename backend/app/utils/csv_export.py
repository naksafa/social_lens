"""CSV export with protection against CSV/formula injection.

Spreadsheet apps execute cells starting with = + - @ (and tab/CR) as formulas. Any
such text cell is prefixed with a single quote so it is displayed, not executed.
Numeric values (including negatives) are left untouched.
"""

import csv
import io
from collections.abc import Iterable, Sequence

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def escape_cell(value: object) -> object:
    if isinstance(value, str) and value.startswith(_DANGEROUS):
        return "'" + value
    return value


def to_csv(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([escape_cell(h) for h in header])
    for row in rows:
        writer.writerow(["" if v is None else escape_cell(v) for v in row])
    return buf.getvalue()
