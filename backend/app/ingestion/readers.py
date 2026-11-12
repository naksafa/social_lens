"""Read CSV/XLSX exports into raw string DataFrames.

Real exports are messy: BOMs, UTF-16 (TikTok), semicolon delimiters (EU locales),
description rows above the header (LinkedIn), multiple sheets. Everything is read
as raw values first; typed parsing happens during normalization.
"""

import csv
import io
from dataclasses import dataclass, field

import pandas as pd

from app.core.exceptions import InvalidDatasetError, UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = (".csv", ".xlsx")
_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252", "latin-1")
_HEADER_SCAN_ROWS = 15
MAX_ROWS = 100_000


@dataclass
class RawTable:
    df: pd.DataFrame
    header_row: int
    sheet_name: str | None = None
    encoding: str | None = None
    delimiter: str | None = None
    duplicate_columns: list[str] = field(default_factory=list)


def read_table(content: bytes, extension: str) -> RawTable:
    ext = extension.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Upload a CSV or XLSX export.",
            {"allowed": list(SUPPORTED_EXTENSIONS)},
        )
    if not content.strip():
        raise InvalidDatasetError("The file is empty.")
    table = _read_csv(content) if ext == ".csv" else _read_xlsx(content)
    if table.df.empty:
        raise InvalidDatasetError("The file has a header but no data rows.")
    if len(table.df) > MAX_ROWS:
        raise InvalidDatasetError(
            f"The file has {len(table.df):,} rows; the maximum is {MAX_ROWS:,}.",
            {"rows": len(table.df)},
        )
    return table


def _decode(content: bytes) -> tuple[str, str]:
    if content[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return content.decode("utf-16"), "utf-16"
    for enc in _ENCODINGS:
        if enc == "utf-16":
            continue
        try:
            return content.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise InvalidDatasetError("Could not decode the file. Save it as UTF-8 CSV and retry.")


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
        return max(counts, key=counts.get)  # type: ignore[arg-type]


def _read_csv(content: bytes) -> RawTable:
    text, encoding = _decode(content)
    delimiter = _sniff_delimiter(text[:20_000])
    try:
        grid = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            header=None,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=True,
            engine="python",
            on_bad_lines="skip",
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InvalidDatasetError("The CSV file could not be parsed.", {"reason": str(exc)}) from exc
    table = _promote_header(grid)
    table.encoding, table.delimiter = encoding, delimiter
    return table


def _read_xlsx(content: bytes) -> RawTable:
    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, dtype=object)
    except Exception as exc:  # openpyxl raises many types for corrupt files
        raise InvalidDatasetError("The XLSX file could not be opened.", {"reason": str(exc)}) from exc
    best: RawTable | None = None
    for name, grid in sheets.items():
        grid = grid.dropna(how="all").dropna(axis=1, how="all")
        if grid.empty:
            continue
        candidate = _promote_header(grid.reset_index(drop=True))
        candidate.sheet_name = str(name)
        # Prefer the sheet with the most data cells (post-level sheet over summary sheets).
        if best is None or candidate.df.size > best.df.size:
            best = candidate
    if best is None:
        raise InvalidDatasetError("The workbook contains no data.")
    return best


def _looks_like_label(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text.replace(",", ""))
        return False
    except ValueError:
        return True


def _detect_header_row(grid: pd.DataFrame) -> int:
    """Pick the first row, among the first rows, that is mostly non-numeric labels
    and spans (nearly) the full width. Skips description/title rows above headers."""
    width = grid.shape[1]
    best_row, best_score = 0, -1.0
    for i in range(min(_HEADER_SCAN_ROWS, len(grid))):
        row = grid.iloc[i]
        labels = sum(_looks_like_label(v) for v in row)
        filled = sum(_looks_like_label(v) or str(v).strip() not in ("", "nan", "None") for v in row)
        if filled == 0:
            continue
        score = labels / width
        if score > best_score + 0.2:  # later rows must be clearly better to win
            best_row, best_score = i, score
        if score >= 0.8:
            break
    return best_row


def _promote_header(grid: pd.DataFrame) -> RawTable:
    header_row = _detect_header_row(grid)
    headers = [
        str(h).strip() if _looks_like_label(h) or str(h).strip() else f"column_{i + 1}"
        for i, h in enumerate(grid.iloc[header_row])
    ]
    headers = [h if h and h.lower() not in ("nan", "none") else f"column_{i + 1}" for i, h in enumerate(headers)]

    seen: dict[str, int] = {}
    unique_headers, duplicates = [], []
    for h in headers:
        key = h.lower()
        if key in seen:
            seen[key] += 1
            duplicates.append(h)
            unique_headers.append(f"{h} ({seen[key]})")
        else:
            seen[key] = 1
            unique_headers.append(h)

    df = grid.iloc[header_row + 1 :].copy()
    df.columns = unique_headers
    df = df.dropna(how="all")
    df = df[~df.apply(lambda r: all(str(v).strip() in ("", "nan", "None") for v in r), axis=1)]
    # Drop fully empty unnamed columns.
    empty_cols = [
        c
        for c in df.columns
        if c.startswith("column_") and df[c].map(lambda v: str(v).strip() in ("", "nan", "None")).all()
    ]
    df = df.drop(columns=empty_cols).reset_index(drop=True)
    return RawTable(df=df, header_row=header_row, duplicate_columns=list(dict.fromkeys(duplicates)))
