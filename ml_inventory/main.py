from __future__ import annotations
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import requests
from urllib.parse import urlsplit, urlunsplit

from ml_inventory.ml_api import MercadoLibreAPI
from ml_inventory.scraper import probe_stock_from_page
from ml_inventory.report import ExcelReport, Row

ITEMS_API = "https://api.mercadolibre.com/items/{}"


def strip_tracking(u: str) -> str:
    parts = urlsplit(u)
    # remove query and fragment
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def parse_item_id_from_url(u: str) -> Optional[str]:
    # e.g. /MLM-756568095-... or /MLM756568095
    m = re.search(r"(MLM-?\d{6,15})", u, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).replace("-", "").upper()


@dataclass
class InputRow:
    url: str
    brand: str
    sku: str


def read_config(path: str = "config/urls.csv") -> List[InputRow]:
    out: List[InputRow] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            out.append(
                InputRow(
                    url=strip_tracking(r["url"].strip()),
                    brand=(r.get("brand") or "").strip(),
                    sku=(r.get("sku") or "").strip(),
                )
            )
    return out


def fetch_public_item(item_id: str) -> Optional[dict]:
    try:
        resp = requests.get(ITEMS_API.format(item_id), timeout=15)
        if resp.ok:
            data = resp.json()
            if isinstance(data, dict) and not data.get("error"):
                return data
    except Exception:
        pass
    return None


def resolve_inventory(api: MercadoLibreAPI, row: InputRow) -> Tuple[str, str, str]:
    # 1) API pública (sin OAuth)
    item_id = parse_item_id_from_url(row.url) or api.parse_item_id_from_url(row.url)
    if item_id:
        data = fetch_public_item(item_id)
        if data:
            available = int(data.get("available_quantity", 0) or 0)
            title = data.get("title") or row.url
            sku = row.sku or data.get("seller_custom_field") or item_id
            return sku, title, ("si" if available > 0 else "no")

    # 2) (Opcional) API con OAuth si la tuvieras configurada
    try:
        if item_id:
            item = api.get_item(item_id)
            if item:
                available = int(item.get("available_quantity", 0) or 0)
                title = item.get("title") or row.url
                sku = row.sku or item.get("seller_custom_field") or item_id
                return sku, title, ("si" if available > 0 else "no")
    except Exception:
        pass

    # 3) Fallback: scraping
    title, has_stock, badge = probe_stock_from_page(row.url)
    title_for_report = title or row.url
    if has_stock is True:
        value = "si"
    elif has_stock is False:
        value = "no"
    else:
        value = badge or ""
    return (row.sku or row.url, title_for_report, value)


def main():
    cfg = read_config()
    api = MercadoLibreAPI()
    today = datetime.now()

    rows: List[Row] = []
    for item in cfg:
        sku, product, value = resolve_inventory(api, item)
        rows.append(Row(sku=sku, product=product, brand=item.brand, value=value))

    path = ExcelReport(today).write(rows)
    print(f"Wrote: {path}")


if __name__ == "__main__":
    main()

