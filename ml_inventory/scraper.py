from typing import Optional, Tuple
import json
import re
import requests
from bs4 import BeautifulSoup

# Headers amables
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}
API_ITEM_URL = "https://api.mercadolibre.com/items/{}"

# -------- utilidades ----------
def canonicalize(url: str) -> str:
    return re.sub(r"#.*$", "", url.strip())

def extract_item_id(url: str) -> Optional[str]:
    """
    Devuelve el ID de item (formato API): 'MLM123456789'
    Acepta 'MLM-123456789' o 'MLM123456789' dentro de la URL.
    """
    m = re.search(r"(MLM-?\d{6,})", url, flags=re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).upper()
    return raw.replace("-", "")

def _probe_items_api(item_id: str) -> Optional[Tuple[Optional[str], Optional[bool], str]]:
    """
    Llama la API pública de Items (sin token).
    Devuelve (title, has_stock, fuente) o None si no se puede decidir.
    """
    try:
        r = requests.get(API_ITEM_URL.format(item_id), timeout=20, headers={"User-Agent": HEADERS["User-Agent"]})
        if r.status_code != 200:
            return None
        data = r.json()
        title = data.get("title")
        aq = data.get("available_quantity")
        if isinstance(aq, int):
            return title, (aq > 0), "api:available_quantity"
        status = (data.get("status") or "").lower()
        if status == "closed":
            return title, False, "api:status_closed"
        return title, None, "api:indeterminado"
    except Exception:
        return None

def _jsonld_has_stock(soup: BeautifulSoup) -> Optional[Tuple[bool, str]]:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
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

def _text_flags(text_low: str) -> Optional[Tuple[bool, str]]:
    pos = ("stock disponible", "últimas disponibles", "disponible para envío", "hay stock")
    neg = ("sin stock", "agotado", "no disponible", "stock no disponible")
    for n in neg:
        if n in text_low:
            return False, n
    for p in pos:
        if p in text_low:
            return True, p
    return None

# -------- función principal ----------
def probe_stock_from_page(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    """
    Devuelve (título, tiene_stock, pista)
    - título: str o None
    - tiene_stock: True / False / None
    - pista: de dónde salió la decisión
    """
    clean = canonicalize(url)
    item_id = extract_item_id(clean)

    # 1) Primero API si hay item_id
    if item_id:
        api_res = _probe_items_api(item_id)
        if api_res is not None:
            return api_res

    # 2) HTML
    try:
        r = requests.get(clean, headers=HEADERS, timeout=timeout)
        # No levantar excepción por 400/403; a veces devuelven HTML útil
    except requests.RequestException:
        return None, None, None

    soup = BeautifulSoup(r.text, "lxml")

    # Título
    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # JSON-LD
    jl = _jsonld_has_stock(soup)
    if jl is not None:
        has, badge = jl
        return title, has, badge

    # Texto visible
    text_low = soup.get_text(" ", strip=True).lower()
    tf = _text_flags(text_low)
    if tf is not None:
        has, badge = tf
        return title, has, badge

    return title, None, None
