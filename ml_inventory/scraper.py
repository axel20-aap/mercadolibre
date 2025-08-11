from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
}

# Devuelve (title, has_stock, stock_text)
def probe_stock_from_page(url: str, timeout: int = 30) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    title = soup.title.text.strip() if soup.title else None

    texts = " ".join(t.get_text(" ", strip=True) for t in soup.find_all())
    texts_low = texts.lower()

    has_stock = None
    stock_text = None
    if "+50" in texts or "+ 50" in texts:
        has_stock = True
        stock_text = "+50"
    elif "últimas disponibles" in texts_low or "stock disponible" in texts_low or "disponibles" in texts_low:
        has_stock = True
        stock_text = "en stock"
    elif "sin stock" in texts_low or "no disponible" in texts_low or "agotado" in texts_low:
        has_stock = False
        stock_text = "sin stock"

    return title, has_stock, stock_text
