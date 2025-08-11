from __future__ import annotations
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from ml_inventory.ml_api import MercadoLibreAPI
from ml_inventory.scraper import probe_stock_from_page
from ml_inventory.report import ExcelReport, Row


@dataclass
class InputRow:
    url: str
    brand: str
    sku: str


def read_config(path: str = "config/urls.csv") -> List[InputRow]:
    out: List[InputRow] = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            out.append(
                InputRow(
                    url=r["url"].strip(),
                    brand=(r.get("brand") or "").strip(),
                    sku=(r.get("sku") or "").strip(),
                )
            )
    return out


def resolve_inventory(api: MercadoLibreAPI, row: InputRow) -> Tuple[str, str, str]:
    """
    Devuelve (sku_o_id, titulo, valor) donde valor es 'sí' / 'no' o un badge
    si no se pudo determinar con certeza.
    """
    item_id = api.parse_item_id_from_url(row.url)
    title_for_report: Optional[str] = None

    # 1) Intento vía API usando el ID presente en la URL
    if item_id:
        try:
            item = api.get_item(item_id)
            available = int(item.get("available_quantity", 0))
            title_for_report = item.get("title") or row.url
            return (
                row.sku or item.get("seller_custom_field") or item_id,
                title_for_report,
                ("sí" if available > 0 else "no"),
            )
        except Exception:
            # Si falla, caemos al siguiente método
            pass

    # 2) Intento vía API buscando por SKU
    if row.sku:
        try:
            res = api.search_items_by_sku(row.sku)
            results = res.get("results") or []
            if results:
                item_id2 = results[0]
                item = api.get_item(item_id2)
                available = int(item.get("available_quantity", 0))
                title_for_report = item.get("title") or row.url
                return (row.sku, title_for_report, ("sí" if available > 0 else "no"))
        except Exception:
            pass

    # 3) Fallback scraping de la página pública
    title, has_stock, badge = probe_stock_from_page(row.url)
    title_for_report = title or row.url
    if has_stock is True:
        value = "sí"
    elif has_stock is False:
        value = "no"
    else:
        value = badge or ""

    return (row.sku or row.url, title_for_r



