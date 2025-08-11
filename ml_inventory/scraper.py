from typing import Optional, Tuple
import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

# Solo quitamos el fragmento (#...) para evitar 400 y NO perder ?seller_id=...
def canonicalize(url: str) -> str:
    return re.sub(r"#.*$", "", url.strip())

def _text_has_stock_flags(text_low: str) -> Optional[Tuple[bool, str]]:
    POS = (
        "stock disponible",
        "disponibilidad inmediata",
        "últimas disponibles",
        "disponible para envío",
        "hay stock",
    )
    NEG = (
        "sin stock",
        "no hay stock",
        "agotado",
        "stock no disponible",
        "sin disponibilidad",
    )
    for p in NEG:
        if p in text_low:
            return False, p
    for p in POS:
        if p in text_low:
            return True, p
    return None

def _jsonld_has_stock(soup: BeautifulSoup) -> Optional[Tuple[bool, str]]:
    # Muchos listados incluyen availability en JSON-LD
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or "")
        except Exception:
            continue
        if isinstance(data, dict):
            offers = data.get("offers")
            if isinstance(offers, dict):
                av = (offers.get("availability") or "").lower()
                if "instock" in av:
                    return True, "jsonld:instock"
                if "outofstock" in av:
                    return False, "jsonld:outofstock"
        # a veces es una lista
        if isinstance(data, list):
            for d in data:
                if not isinstance(d, dict):
                    continue
                offers = d.get("offers")
                if isinstance(offers, dict):
                    av = (offers.get("availability") or "").lower()
                    if "instock" in av:
                        return True, "jsonld:instock"
                    if "outofstock" in av:
                        return False, "jsonld:outofstock"
    return None

def probe_stock_from_page(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    """
    Devuelve (title, has_stock, badge)
      - title: nombre del producto (o None)
      - has_stock: True/False/None
      - badge: texto que disparó la detección
    """
    clean = canonicalize(url)
    r = requests.get(clean, headers=HEADERS, timeout=timeout)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # Título del producto: primero <h1>, si no hay, usa <title>
    title_tag = soup.find("h1")
    title = (title_tag.get_text(strip=True) if title_tag else None) or \
            ((soup.title.get_text(strip=True) if soup.title else None))

    # 1) Intento por JSON-LD
    js = _jsonld_has_stock(soup)
    if js is not None:
        has_stock, badge = js
        return title, has_stock, badge

    # 2) Intento por texto visible en la página
    text_low = soup.get_text(" ", strip=True).lower()
    res = _text_has_stock_flags(text_low)
    if res is not None:
        has_stock, badge = res
        return title, has_stock, badge

    # No pudimos determinar
    return title, None, None

