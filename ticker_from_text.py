"""Extrae símbolos tipo ticker desde texto pegado o OCR de Trade Ideas / scanners."""
from __future__ import annotations

import re
from typing import List

# Palabras que parecen tickers pero no lo son
_STOP = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE",
    "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "MAN", "NEW", "NOW", "OLD",
    "SEE", "WAY", "WHO", "BOY", "DID", "ITS", "LET", "PUT", "SAY", "SHE", "TOO", "USE",
    "GAP", "RVOL", "RSI", "PMH", "VWAP", "ORB", "ETF", "USA", "USD", "CEO", "CFO",
    "IPO", "ATH", "ATL", "HALT", "OPEN", "CLOSE", "HIGH", "LOW", "LAST", "BID", "ASK",
    "VOL", "AVG", "CHG", "PCT", "PRE", "POST", "AH", "PM", "NYSE", "NASA", "HTTP",
    "HTTPS", "WWW", "COM", "NET", "ORG", "PDF", "CSV", "API", "SDK", "UI", "UX",
    "LONG", "SHORT", "BUY", "SELL", "HOLD", "STOP", "TIME", "DATE", "TRUE", "FALSE",
    "NONE", "NULL", "SCAN", "LIST", "TOP", "MIN", "MAX", "SUM", "AVG",
}


def extract_tickers(text: str, max_n: int = 40) -> List[str]:
    if not text:
        return []
    # Prefer patterns like 2-5 uppercase letters as whole words
    found = re.findall(r"\b([A-Z]{1,5})\b", text.upper())
    out: List[str] = []
    seen = set()
    for t in found:
        if t in _STOP or t.isdigit():
            continue
        if len(t) < 2:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= max_n:
            break
    return out


def ocr_image_to_text(file_bytes: bytes) -> str:
    """OCR opcional (pytesseract + Pillow). Si no está instalado, devuelve ''."""
    try:
        from io import BytesIO
        from PIL import Image
        import pytesseract
        img = Image.open(BytesIO(file_bytes))
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""
