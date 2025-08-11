from __future__ import annotations
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from ml_inventory.scraper import probe_stock_from_page, canonicalize
from ml_inventory.report import ExcelReport, Row

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
            out.append(InputRow(
                url=r["url"].strip(),
                brand=(r.get("brand") or "").strip(),
                sku=(r.get("sku") or "").strip(),
            ))
    return out

def resolve_inventory(row: InputRow) -> Tuple[str, str, str]:
    url = canonicalize(row.url)
    title, has_stock, _badge = probe_stock_from_page(url)

    product_for_report = title or url
    value = "sí" if has_stock else ("no" if has_stock is False else "?")
    sku_for_report = row.sku or url
    return sku_for_report, product_for_report, value

def main():
    cfg = read_config()
    today = datetime.now()

    rows: List[Row] = []
    for r in cfg:
        sku, product, value = resolve_inventory(r)
        rows.append(Row(sku=sku, product=product, brand=r.brand, value=value))

    path = ExcelReport(today).write(rows)
    print(f"Wrote: {path}")

if __name__ == "__main__":
    main()
