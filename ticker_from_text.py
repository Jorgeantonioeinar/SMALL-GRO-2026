"""Extrae símbolos desde texto pegado, OCR o CSV export de Moomoo/Webull."""
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
}


def extract_tickers(text: str, max_n: int = 50) -> List[str]:
    if not text or not str(text).strip():
        return []
    # Normalizar: quitar puntos suspensivos y comillas
    text = str(text).replace("…", " ").replace("...", " ")
    text = text.replace(",", " ").replace(";", " ").replace("\t", " ")
    # Mayúsculas y tokens 1-5 letras (opcional dígito al final tipo 5G no)
    found = re.findall(r"\b([A-Za-z]{1,5})\b", text)
    out: List[str] = []
    seen = set()
    for raw in found:
        t = raw.upper().strip()
        if t in _STOP or t.isdigit() or len(t) < 2:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= max_n:
            break
    return out


def extract_tickers_from_csv(file_bytes: bytes, max_n: int = 50) -> List[str]:
    """Lee export Moomoo/Webull: columna Symbol / Ticker / symbol."""
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace")
    # Intento CSV con header
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
                    val = (row.get(sym_key) or "").strip().upper()
                    # US.AAPL -> AAPL
                    if "." in val:
                        val = val.split(".")[-1]
                    val = re.sub(r"[^A-Z]", "", val)
                    if len(val) >= 1 and len(val) <= 5 and val not in _STOP and val not in seen:
                        seen.add(val)
                        out.append(val)
                    if len(out) >= max_n:
                        break
                if out:
                    return out
    except Exception:
        pass
    # Fallback: regex sobre todo el texto
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
