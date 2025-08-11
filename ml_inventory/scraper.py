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
    # 1) Pide la página con headers de navegador y maneja 4xx/5xx
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        html = r.text
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        badge = f"HTTP{status}" if status else "HTTPERR"
        return None, None, badge

    # 2) Algunas respuestas pueden ser JSON/script (captcha/login). No rompas.
    if html.lstrip().startswith("{") or html.lstrip().startswith("<script"):
        return None, None, "NONHTML"

    # 3) Parse robusto: usa el parser de HTML estándar y captura errores de parseo
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None, None, "PARSE"

    title = soup.title.text.strip() if soup.title else None

    # 4) Heurísticas simples de stock
    texts_low = " ".join(t.get_text(" ", strip=True) for t in soup.find_all()).lower()

    has_stock: Optional[bool] = None
    stock_text: Optional[str] = None

    if "+50" in texts_low or "+ 50" in texts_low or "más de 50" in texts_low or "mas de 50" in texts_low:
        has_stock = True
        stock_text = "+50"
    elif any(s in texts_low for s in ["últimas disponibles", "ultimas disponibles", "en stock", "stock disponible", "disponibles"]):
        has_stock = True
        stock_text = "en stock"
    elif any(s in texts_low for s in ["sin stock", "no disponible", "agotado"]):
        has_stock = False
        stock_text = "sin stock"
    elif any(s in texts_low for s in ["inicia sesión", "inicia sesion", "captcha", "seguridad", "verifica"]):
        # pistas de login/captcha
        return title, None, "LOGIN"

    return title, has_stock, stock_text
