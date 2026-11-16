"""Generate deterministic weekly FMCG sales for fictional branches of UK grocers."""

from datetime import date, timedelta
from itertools import product
from pathlib import Path
from random import Random
import csv
import math

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fmcg"
TITLE = "UK FMCG Store Network Performance"
DISCLAIMER = "SIMULATED SALES  /  FICTIONAL BRANCHES  /  FY2025 · 52 WEEKS"

# Average weekly category units per store and representative unit price in pence.
CATEGORIES = {
    "Ambient grocery": (3100, 265, 0.29),
    "Bakery": (2250, 185, 0.35),
    "Beverages": (2100, 230, 0.29),
    "Chilled and dairy": (3450, 245, 0.25),
    "Fresh produce": (3600, 215, 0.24),
    "Frozen": (1030, 370, 0.27),
    "Household and personal care": (970, 480, 0.36),
}

# Volume and ticket multipliers are scenario assumptions.
RETAILERS = {
    "Tesco": (1.28, 1.01),
    "Asda": (1.12, 0.96),
    "Lidl": (0.88, 0.84),
    "Waitrose": (0.74, 1.22),
    "Aldi": (0.92, 0.82),
}
REGIONS = {"London": 1.16, "South": 1.06, "Midlands": 0.96, "North": 0.98, "Scotland": 0.87}
FORMATS = {"Compact": 0.68, "Standard": 1.0, "Large": 1.42}
FIELDS = (
    "week", "retailer", "region", "store", "format", "category",
    "units", "sales_pence", "prior_sales_pence", "target_pence",
    "profit_pence", "promo_pence",
)


def sales_rows():
    rng = Random(1905)
    for retailer, region, store_format in product(RETAILERS, REGIONS, FORMATS):
        volume, ticket = RETAILERS[retailer]
        store = f"{retailer} · {region} · {store_format}"
        traffic = volume * REGIONS[region] * FORMATS[store_format] * rng.uniform(0.91, 1.09)
        growth = rng.uniform(-0.075, 0.13)
        for category, (base_units, price, margin) in CATEGORIES.items():
            for week in range(52):
                start = date(2024, 12, 30) + timedelta(weeks=week)
                seasonality = 1 + 0.06 * math.cos(math.tau * (week - 48) / 52)
                if week in (47, 48, 49, 50, 51):
                    seasonality *= 1.30 if category in ("Beverages", "Bakery", "Frozen") else 1.18
                prior_units = round(base_units * traffic * seasonality * rng.uniform(0.92, 1.08))
                promo_share = rng.uniform(0.08, 0.34)
                units = round(prior_units * (1 + growth + (promo_share - 0.18) * 0.26) * rng.uniform(0.94, 1.06))
                list_price = round(price * ticket * 1.026)
                promo_units = round(units * promo_share)
                promo = promo_units * round(list_price * 0.83)
                sales = (units - promo_units) * list_price + promo
                prior = round(prior_units * price * ticket * 0.965)
                target = round(prior * 1.04)
                cost = units * round(list_price * (1 - margin))
                yield (start.isoformat(), retailer, region, store, store_format, category,
                       units, sales, prior, target, sales - cost, promo)


def export():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "weekly_sales.csv"
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(FIELDS)
        writer.writerows(sales_rows())
    return path


if __name__ == "__main__":
    print(export())
