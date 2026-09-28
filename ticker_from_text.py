"""Extrae símbolos desde texto Webull/Moomoo, OCR o CSV."""
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
    "CHART", "GAINERS", "LOSERS", "ACTIVE", "WEBULL", "MOOMOO", "NO",
}

# Webull a menudo pone el TICKER solo en una línea (2-5 letras mayúsculas)
_RE_TICKER_LINE = re.compile(r"^\s*([A-Za-z]{1,5})\s*$")
_RE_TICKER_TOKEN = re.compile(r"\b([A-Za-z]{1,5})\b")
_RE_PCT = re.compile(r"[+\-]?\d+\.?\d*\s*%")
_RE_NUM = re.compile(r"^[\d,\.]+[KMB]?$", re.I)


def _clean_token(t: str) -> str:
    t = (t or "").upper().strip()
    t = t.replace("$", "").strip()
    if "." in t and not t.startswith("BRK"):
        # US.AAPL -> AAPL
        t = t.split(".")[-1]
    t = re.sub(r"[^A-Z]", "", t)
    return t


def _is_ticker(t: str) -> bool:
    if not t or len(t) < 1 or len(t) > 5:
        return False
    if t in _STOP or t.isdigit():
        return False
    if len(t) < 2:
        return False
    return t.isalpha()


def extract_tickers(text: str, max_n: int = 50) -> List[str]:
    """Robusto ante pegado Webull (nombre / ticker / % en líneas distintas)."""
    if not text or not str(text).strip():
        return []
    text = str(text).replace("\xa0", " ").replace("…", " ").replace("...", " ")
    lines = text.splitlines()
    out: List[str] = []
    seen = set()

    def add(tok: str):
        tok = _clean_token(tok)
        if _is_ticker(tok) and tok not in seen:
            seen.add(tok)
            out.append(tok)

    # 1) Líneas que son SOLO el ticker (patrón típico Webull)
    for line in lines:
        line = line.strip()
        if not line or _RE_PCT.search(line) or _RE_NUM.match(line.replace(",", "")):
            continue
        m = _RE_TICKER_LINE.match(line)
        if m:
            add(m.group(1))

    # 2) Tokens en el texto completo (por si viene en una sola línea)
    if len(out) < 3:
        cleaned = _RE_PCT.sub(" ", text)
        for m in _RE_TICKER_TOKEN.finditer(cleaned):
            add(m.group(1))
            if len(out) >= max_n:
                break

    return out[:max_n]


def extract_tickers_from_csv(file_bytes: bytes, max_n: int = 50) -> List[str]:
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace")
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames:
            keys = {k.strip().lower(): k for k in reader.fieldnames if k}
            sym_key = None
            for cand in ("symbol", "ticker", "sym", "code", "stock"):
                if cand in keys:
                    sym_key = keys[cand]
                    break
            out: List[str] = []
            seen = set()
            if sym_key:
                for row in reader:
                    val = _clean_token(row.get(sym_key) or "")
                    if _is_ticker(val) and val not in seen:
                        seen.add(val)
                        out.append(val)
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
        img = Image.open(BytesIO(file_bytes))
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""
