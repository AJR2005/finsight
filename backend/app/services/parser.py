"""Turns bank / UPI statements (CSV, Excel or PDF) into a list of normalised transactions.

Indian bank exports all use different column names (HDFC says "Narration" and
"Withdrawal Amt.", SBI says "Description" and "Debit", ICICI says "Transaction Remarks"...),
so instead of one parser per bank we locate the header row and map columns by keyword.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

DATE_KEYS = ("txn date", "transaction date", "tran date", "value date", "date")
DESC_KEYS = ("narration", "description", "remarks", "particulars", "details", "transaction details", "merchant")
DEBIT_KEYS = ("withdrawal", "debit", "dr", "paid out", "money out")
CREDIT_KEYS = ("deposit", "credit", "cr", "paid in", "money in")
AMOUNT_KEYS = ("amount", "amt", "transaction amount")
TYPE_KEYS = ("type", "dr/cr", "cr/dr", "debit/credit")


class StatementError(ValueError):
    pass


@dataclass
class ParsedTxn:
    date: date
    description: str
    amount: float  # positive = credit, negative = debit

    @property
    def fingerprint(self) -> str:
        raw = f"{self.date.isoformat()}|{self.description.strip().lower()}|{self.amount:.2f}"
        return hashlib.sha256(raw.encode()).hexdigest()


def with_fingerprints(txns: list[ParsedTxn]) -> list[tuple[ParsedTxn, str]]:
    """Pairs each row with a dedupe key.

    Two identical rows in one statement (e.g. two ₹20 chais on the same day) are both real, so the
    n-th repeat gets its own key. Re-uploading the same statement still matches every key.
    """
    counts: dict[str, int] = {}
    out = []
    for t in txns:
        n = counts.get(t.fingerprint, 0)
        counts[t.fingerprint] = n + 1
        out.append((t, t.fingerprint if n == 0 else hashlib.sha256(f"{t.fingerprint}#{n}".encode()).hexdigest()))
    return out


def parse_statement(filename: str, content: bytes) -> list[ParsedTxn]:
    name = filename.lower()
    if name.endswith(".pdf"):
        frames = _pdf_tables(content)
    elif name.endswith((".xls", ".xlsx")):
        frames = [pd.read_excel(io.BytesIO(content), header=None, dtype=str)]
    elif name.endswith((".csv", ".txt")):
        frames = [_read_csv(content)]
    else:
        raise StatementError("Unsupported file type. Upload a CSV, Excel or PDF statement.")

    txns: list[ParsedTxn] = []
    for raw in frames:
        txns.extend(_parse_frame(raw))
    if not txns and name.endswith(".pdf"):
        txns = _parse_pdf_text(content)
    if not txns:
        raise StatementError("Couldn't find any transactions. Check the file has date, description and amount columns.")
    return txns


def _read_csv(content: bytes) -> pd.DataFrame:
    text = content.decode("utf-8-sig", errors="replace")
    # Header-less read so we can find the real header row below bank preambles.
    return pd.read_csv(io.StringIO(text), header=None, dtype=str, skip_blank_lines=True,
                       on_bad_lines="skip", engine="python")


def _pdf_tables(content: bytes) -> list[pd.DataFrame]:
    import pdfplumber

    frames = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        rows: list[list[str]] = []
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend([[c or "" for c in row] for row in table])
        if rows:
            width = max(len(r) for r in rows)
            frames.append(pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str))
    return frames


def _norm(cell) -> str:
    return re.sub(r"\s+", " ", str(cell or "")).strip().lower()


def _match(header: str, keys: tuple[str, ...]) -> bool:
    words = re.split(r"[^a-z/]+", header)
    return any(k == header or (" " in k and k in header) or k in words for k in keys)


def _find_columns(row: list[str]) -> dict[str, int] | None:
    cols: dict[str, int] = {}
    for i, h in enumerate(row):
        if not h:
            continue
        if "date" not in cols and _match(h, DATE_KEYS):
            cols["date"] = i
        elif "desc" not in cols and _match(h, DESC_KEYS):
            cols["desc"] = i
        elif "debit" not in cols and _match(h, DEBIT_KEYS):
            cols["debit"] = i
        elif "credit" not in cols and _match(h, CREDIT_KEYS):
            cols["credit"] = i
        elif "amount" not in cols and _match(h, AMOUNT_KEYS):
            cols["amount"] = i
        elif "type" not in cols and _match(h, TYPE_KEYS):
            cols["type"] = i
    has_money = ("debit" in cols or "credit" in cols) or "amount" in cols
    return cols if {"date", "desc"} <= cols.keys() and has_money else None


def _to_float(value) -> float | None:
    s = str(value or "").strip()
    if not s or s.lower() in ("nan", "none", "-"):
        return None
    negative = s.startswith("(") or s.startswith("-")
    is_dr = bool(re.search(r"\bdr\b", s, re.I))
    s = re.sub(r"[^\d.]", "", s)
    if not s or s == ".":
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if negative or is_dr else num


def _to_date(value) -> date | None:
    s = str(value or "").strip()
    if not s or s.lower() == "nan":
        return None
    # ISO dates (2024-05-31) must not be read day-first.
    dayfirst = not re.match(r"^\d{4}-\d{2}-\d{2}", s)
    d = pd.to_datetime(s, dayfirst=dayfirst, errors="coerce")
    return None if pd.isna(d) else d.date()


def _parse_frame(raw: pd.DataFrame) -> list[ParsedTxn]:
    raw = raw.fillna("")
    header_idx, cols = None, None
    for idx in range(min(len(raw), 40)):
        cols = _find_columns([_norm(c) for c in raw.iloc[idx].tolist()])
        if cols:
            header_idx = idx
            break
    if header_idx is None:
        return []

    txns = []
    for _, row in raw.iloc[header_idx + 1:].iterrows():
        values = row.tolist()
        d = _to_date(values[cols["date"]])
        desc = re.sub(r"\s+", " ", str(values[cols["desc"]])).strip()
        if d is None or not desc:
            continue
        if "debit" in cols or "credit" in cols:
            debit = _to_float(values[cols["debit"]]) if "debit" in cols else None
            credit = _to_float(values[cols["credit"]]) if "credit" in cols else None
            if debit:
                amount = -abs(debit)
            elif credit:
                amount = abs(credit)
            elif "amount" in cols:
                amount = _to_float(values[cols["amount"]]) or 0
            else:
                continue
        else:
            amount = _to_float(values[cols["amount"]])
            if amount is None:
                continue
            if "type" in cols:
                kind = _norm(values[cols["type"]])
                if kind.startswith(("dr", "debit", "withdraw")):
                    amount = -abs(amount)
                elif kind.startswith(("cr", "credit", "deposit")):
                    amount = abs(amount)
        if amount == 0:
            continue
        txns.append(ParsedTxn(d, desc[:500], round(amount, 2)))
    return txns


LINE_RE = re.compile(
    r"^(?P<date>\d{1,2}[/\-. ](?:\d{1,2}|[A-Za-z]{3})[/\-. ]\d{2,4})\s+(?P<desc>.+?)\s+"
    r"(?P<amount>[\d,]+\.\d{2})\s*(?P<type>Dr|Cr|DR|CR)?\b"
)


def _parse_pdf_text(content: bytes) -> list[ParsedTxn]:
    """Fallback for PDFs without ruling lines (e.g. many UPI app statements)."""
    import pdfplumber

    txns = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = LINE_RE.match(line.strip())
                if not m:
                    continue
                d = _to_date(m["date"])
                amount = float(m["amount"].replace(",", ""))
                desc = m["desc"].strip()
                credit = (m["type"] or "").lower() == "cr" or re.search(r"\b(received|credited|refund)\b", desc, re.I)
                if d:
                    txns.append(ParsedTxn(d, desc, amount if credit else -amount))
    return txns
