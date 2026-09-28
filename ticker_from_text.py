"""Extrae símbolos desde texto Webull/Moomoo, CSV o lista simple."""
from __future__ import annotations

import csv
import io
import re
from typing import List

_STOP = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE",
    "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "MAN", "NEW", "NOW", "OLD",
    "SEE", "WAY", "WHO", "BOY", "DID", "ITS", "LET", "PUT", "SAY", "SHE", "TOO", "USE",
    "GAP", "RVOL", "RSI", "PMH", "VWAP", "ORB", "ETF", "USA", "USD", "CEO", "CFO",
    "IPO", "ATH", "ATL", "HALT", "OPEN", "CLOSE", "HIGH", "LOW", "LAST", "BID", "ASK",
    "VOL", "AVG", "CHG", "PCT", "PRE", "POST", "AH", "PM", "NYSE", "NASA", "HTTP",
    "HTTPS", "WWW", "COM", "NET", "ORG", "PDF", "CSV", "API", "SDK", "UI", "UX",
    "LONG", "SHORT", "BUY", "SELL", "HOLD", "STOP", "TIME", "DATE", "TRUE", "FALSE",
    "NONE", "NULL", "SCAN", "LIST", "TOP", "MIN", "MAX", "SUM", "NAME", "PRICE",
    "SYMBOL", "VOLUME", "CHANGE", "MARKET", "CAP", "TURN", "OVER", "INDUSTRY",
    "RATIO", "RANGE", "LOSS", "PREV", "SIZE", "RATE", "FROM", "WITH", "THIS",
    "INC", "LTD", "CORP", "PLC", "CO", "GROUP", "HOLDINGS", "HOLDING", "TECHNOLOGY",
    "TECHNOLOGIES", "LIMITED", "INCORPORATED", "INTERNATIONAL", "GLOBAL", "BIO",
    "PREMARKET", "AFTER", "HOURS", "MINUTES", "WEEKS", "MONTH", "MONTHS", "SPARK",
    "CHART", "GAINERS", "LOSERS", "ACTIVE", "WEBULL", "MOOMOO", "NO", "TICKER",
}

_RE_TICKER_LINE = re.compile(r"^\s*([A-Za-z]{1,5})\s*$")
_RE_TICKER_TOKEN = re.compile(r"\b([A-Za-z]{1,5})\b")
_RE_PCT = re.compile(r"[+\-]?\d+\.?\d*\s*%")
_RE_NUM = re.compile(r"^[\d,\.]+[KMBT]?$", re.I)


def _clean_token(t: str) -> str:
    t = (t or "").upper().strip()
    if "." in t:
        t = t.split(".")[-1]
    t = re.sub(r"[^A-Z]", "", t)
    return t


def _is_ticker(t: str) -> bool:
    if not t or len(t) < 2 or len(t) > 5:
        return False
    if t in _STOP or not t.isalpha():
        return False
    return True


def extract_tickers(text: str, max_n: int = 80) -> List[str]:
    if not text or not str(text).strip():
        return []
    text = str(text).replace("\xa0", " ").replace("…", " ")
    lines = text.splitlines()
    out: List[str] = []
    seen = set()

    def add(tok: str):
        tok = _clean_token(tok)
        if _is_ticker(tok) and tok not in seen:
            seen.add(tok)
            out.append(tok)

    for line in lines:
        line = line.strip()
        if not line or _RE_PCT.search(line):
            continue
        if _RE_NUM.match(line.replace(",", "")):
            continue
        m = _RE_TICKER_LINE.match(line)
        if m:
            add(m.group(1))

    if len(out) < 3:
        cleaned = _RE_PCT.sub(" ", text)
        for m in _RE_TICKER_TOKEN.finditer(cleaned):
            add(m.group(1))
            if len(out) >= max_n:
                break
    return out[:max_n]


def extract_tickers_from_csv(file_bytes: bytes, max_n: int = 80) -> List[str]:
    """CSV Moomoo/Webull: columna Symbol/Ticker, o primera columna."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except Exception:
            text = file_bytes.decode("utf-8", errors="replace")
    out: List[str] = []
    seen = set()

    def add(val: str):
        tok = _clean_token(val)
        if _is_ticker(tok) and tok not in seen:
            seen.add(tok)
            out.append(tok)

    # Sniffer dialect
    try:
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if reader.fieldnames:
            keys = {(k or "").strip().lower(): k for k in reader.fieldnames if k}
            sym_key = None
            for cand in ("symbol", "ticker", "sym", "code", "stock", "符号"):
                if cand in keys:
                    sym_key = keys[cand]
                    break
            # a veces "Symbol/Name"
            if not sym_key:
                for lk, orig in keys.items():
                    if "symbol" in lk or "ticker" in lk:
                        sym_key = orig
                        break
            if sym_key:
                for row in reader:
                    raw = (row.get(sym_key) or "").strip()
                    # "KNRX Lexicon" or "KNRX"
                    first = raw.split()[0] if raw else ""
                    add(first)
                    if len(out) >= max_n:
                        return out
                if out:
                    return out
    except Exception:
        pass

    # Primera columna sin header útil
    try:
        reader2 = csv.reader(io.StringIO(text))
        rows = list(reader2)
        start = 0
        if rows and rows[0] and re.search(r"symbol|ticker|name", (rows[0][0] or ""), re.I):
            start = 1
        for row in rows[start:]:
            if not row:
                continue
            add(row[0].split()[0])
            if len(out) >= max_n:
                break
        if out:
            return out
    except Exception:
        pass

    return extract_tickers(text, max_n=max_n)


def ocr_image_to_text(file_bytes: bytes) -> str:
    try:
        from io import BytesIO
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(BytesIO(file_bytes))) or ""
    except Exception:
        return ""
