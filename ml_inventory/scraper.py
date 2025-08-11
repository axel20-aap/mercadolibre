from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def probe_stock_from_page(url: str, timeout: int = 30) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    # Intenta pedir la página; si falla, no rompas el flujo
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        badge = f"HTTP{status}" if status else "HTTPERR"
        return None, None, badge

    soup = BeautifulSoup(r.text, "lxml")
    title = soup.title.text.strip() if soup.title else None

    # Texto plano en minúsculas para buscar señales de stock
    texts = " ".join(t.get_text(" ", strip=True) for t in soup.find_all()).lower()

    has_stock = None
    stock_text = None

    # heurísticas sencillas
    if "+50" in texts or "+ 50" in texts or "más de 50" in texts or "mas de 50" in texts:
        has_stock = True
        stock_text = "+50"
    elif "últimas disponibles" in texts or "ultimas disponibles" in texts or "en stock" in texts or "stock disponible" in texts or "disponibles" in texts:
        has_stock = True
        stock_text = "en stock"
    elif "sin stock" in texts or "no disponible" in texts or "agotado" in texts:
        has_stock = False
        stock_text = "sin stock"

    return title, has_stock, stock_text
