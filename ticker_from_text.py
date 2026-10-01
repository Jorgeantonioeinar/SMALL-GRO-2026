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



def _parse_pct(val) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s.lower() in ("n/a", "na", "-", "none", ""):
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_float_num(val) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("$", "").upper()
    if not s:
        return None
    mult = 1.0
    if s.endswith("B"):
        mult = 1e9
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1e6
        s = s[:-1]
    elif s.endswith("K"):
        mult = 1e3
        s = s[:-1]
    try:
        return float(s) * mult
    except Exception:
        return None


def extract_rows_from_csv(file_bytes: bytes, max_n: int = 80) -> list:
    """
    CSV Moomoo/Webull → lista de dicts ricos:
      symbol, gap_override (Pre Mkt % o % Chg), rvol_override (Vol Ratio),
      price_hint, float_override (si hay float en CSV).
    Si no hay columnas, cae a solo símbolos.
    """
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except Exception:
            text = file_bytes.decode("utf-8", errors="replace")

    rows_out = []
    seen = set()
    try:
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("sin header")
        keys = {(k or "").strip().lower(): k for k in reader.fieldnames if k}

        def find_key(*cands):
            for c in cands:
                if c in keys:
                    return keys[c]
            for lk, orig in keys.items():
                for c in cands:
                    if c in lk:
                        return orig
            return None

        sym_key = find_key("symbol", "ticker", "sym", "code", "stock")
        # Moomoo premarket gap
        gap_key = find_key(
            "pre mkt % chg", "pre mkt %", "premarket %", "pre-market %",
            "% chg", "chg%", "change %", "percent change", "% change",
        )
        # Prefer Pre Mkt % Chg over session % Chg if both exist
        pre_key = find_key("pre mkt % chg", "pre mkt %", "premarket % chg", "pre-market % chg")
        if pre_key:
            gap_key = pre_key
        rvol_key = find_key("vol ratio", "volume ratio", "rvol", "rel volume", "relative volume")
        price_key = find_key("pre mkt stock price", "pre market price", "last", "price", "last price")
        float_key = find_key("float", "shares float", "float shares")

        if not sym_key:
            # fallback symbols only
            return [{"symbol": s} for s in extract_tickers_from_csv(file_bytes, max_n=max_n)]

        for row in reader:
            raw = (row.get(sym_key) or "").strip()
            if not raw:
                continue
            first = raw.split()[0]
            tok = _clean_token(first)
            if not _is_ticker(tok) or tok in seen:
                continue
            seen.add(tok)
            entry = {"symbol": tok}
            g = _parse_pct(row.get(gap_key)) if gap_key else None
            if g is not None:
                entry["gap_override"] = g
            rv = _parse_pct(row.get(rvol_key)) if rvol_key else None
            if rv is None and rvol_key:
                rv = _parse_float_num(row.get(rvol_key))
            if rv is not None:
                entry["rvol_override"] = rv
            px = _parse_float_num(row.get(price_key)) if price_key else None
            if px is not None:
                entry["price_hint"] = px
            fl = _parse_float_num(row.get(float_key)) if float_key else None
            if fl is not None and fl > 1000:
                entry["float_override"] = fl
            rows_out.append(entry)
            if len(rows_out) >= max_n:
                break
        if rows_out:
            return rows_out
    except Exception:
        pass

    return [{"symbol": s} for s in extract_tickers_from_csv(file_bytes, max_n=max_n)]


def extract_tickers_from_csv(file_bytes: bytes, max_n: int = 80) -> List[str]:
    """CSV Moomoo/Webull: columna Symbol/Ticker, o primera columna. (solo símbolos)"""

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
