from typing import Optional, Tuple
import json
import re
import requests
from bs4 import BeautifulSoup

# ---------- Config ----------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
}
API_ITEM_URL = "https://api.mercadolibre.com/items/{}"

# ---------- Utils ----------
def canonicalize(url: str) -> str:
    # Quitamos solo el fragmento (#...) y espacios
    return re.sub(r"#.*$", "", url.strip())

def extract_item_id(url: str) -> Optional[str]:
    m = re.search(r"/(MLM-\d+)", url, flags=re.IGNORECASE)
    return m.group(1).upper() if m else None

# ---------- JSON-LD / texto ----------
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
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or "")
        except Exception:
            continue
        blocks = data if isinstance(data, list) else [data]
        for d in blocks:
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

# ---------- API pública de items (sin token) ----------
def _probe_via_items_api(item_id: str) -> Optional[Tuple[Optional[str], Optional[bool], Optional[str]]]:
    try:
        r = requests.get(API_ITEM_URL.format(item_id), timeout=20, headers={"User-Agent": HEADERS["User-Agent"]})
        if r.status_code != 200:
            return None
        data = r.json()
        title = data.get("title")
        available = data.get("available_quantity")
        if isinstance(available, int):
            return title, (available > 0), "api:available_quantity"
        # Fallback: algunos catálogos exponen 'sold_quantity' y 'status'
        status = (data.get("status") or "").lower()
        if status == "active":
            # si está activo pero sin 'available_quantity', no nos arriesgamos
            return title, None, None
        if status in ("paused", "closed"):
            return title, False, "api:status"
        return title, None, None
    except Exception:
        return None

# ---------- Entrada principal ----------
def probe_stock_from_page(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    """
    Devuelve (title, has_stock, badge)
    - title: título del producto o None
    - has_stock: True/False/None
    - badge: pista que disparó la decisión (api/jsonld/texto)
    """
    clean = canonicalize(url)
    item_id = extract_item_id(clean)

    # 1) Primero intentamos la API pública (evita 400/403 de página)
    if item_id:
        res = _probe_via_items_api(item_id)
        if res is not None:
            return res

    # 2) Si la API no resolvió, intentamos HTML
    try:
        r = requests.get(clean, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        # Si la página falla pero tenemos item_id, último intento por API
        if item_id:
            res = _probe_via_items_api(item_id)
            if res is not None:
                return res
        return None, None, None

    soup = BeautifulSoup(r.text, "lxml")

    # Título
    title_tag = soup.find("h1")
    title = (title_tag.get_text(strip=True) if title_tag else None) or \
            ((soup.title.get_text(strip=True) if soup.title else None))

    # 2a) JSON-LD
    js = _jsonld_has_stock(soup)
    if js is not None:
        has_stock, badge = js
        return title, has_stock, badge

    # 2b) Texto visible
    text_low = soup.get_text(" ", strip=True).lower()
    res2 = _text_has_stock_flags(text_low)
    if res2 is not None:
        has_stock, badge = res2
        return title, has_stock, badge

    return title, None, None
