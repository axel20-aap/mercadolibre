from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from ml_inventory.scraper import probe_stock_from_page

def read_urls(path: str = "config/urls.csv") -> List[str]:
    """
    Lee la columna 'url' (o la única columna) de config/urls.csv
    """
    out: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return out

    # Detecta si tiene encabezado
    header = [c.strip().lower() for c in rows[0]]
    start = 1 if ("url" in header) else 0

    for row in rows[start:]:
        if not row:
            continue
        url = (row[0] or "").strip()
        if url:
            out.append(url)
    return out

def main():
    urls = read_urls()
    results: List[Tuple[str, str]] = []  # (Producto, Stock)

    for u in urls:
        title, has, _badge = probe_stock_from_page(u)
        producto = title or u
        if has is True:
            stock = "Sí"
        elif has is False:
            stock = "No"
        else:
            stock = "Desconocido"
        results.append((producto, stock))

    # Guardar Excel muy simple
    df = pd.DataFrame(results, columns=["Producto", "Stock"])
    Path("reports").mkdir(parents=True, exist_ok=True)
    fname = f"reports/inventario_simple_{datetime.now():%Y-%m-%d}.xlsx"
    df.to_excel(fname, index=False)
    print(f"Wrote: {fname}")

if __name__ == "__main__":
    main()

