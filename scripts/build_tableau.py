"""Package the simulated FMCG dashboards and their Tableau Hyper extract."""

from datetime import date
from zipfile import ZIP_DEFLATED, ZipFile

from tableau_report import build_workbook
from fmcg_data import DATA, DISCLAIMER, FIELDS as INPUT_COLUMNS, ROOT, TITLE, sales_rows
from report_design import BLUE, ORANGE, PURPLE, TEAL

OUTPUT = ROOT / "tableau"
EXTRACT = "Data/Simulated FMCG Sales.hyper"
FIELDS = {
    "week": ("date", "Week starting"), "retailer": ("string", "Retailer"),
    "region": ("string", "Region"), "store": ("string", "Store"),
    "format": ("string", "Format"), "category": ("string", "Category"),
    "units": ("integer", "Units"), "sales_pence": ("integer", "Net sales in pence"),
    "prior_sales_pence": ("integer", "Prior sales in pence"), "target_pence": ("integer", "Target in pence"),
    "profit_pence": ("integer", "Gross profit in pence"), "promo_pence": ("integer", "Promo sales in pence"),
}
GBP = 'c"£"#,##0;-"£"#,##0'
PERCENT = "p0.0%"
DELTA = "p+0.0%;-0.0%;0.0%"
METRICS = {
    "NetSales": ("Net sales", "SUM([sales_pence]) / 100", GBP),
    "AnnualChange": ("Sales vs prior year", "(SUM([sales_pence]) - SUM([prior_sales_pence])) / SUM([prior_sales_pence])", DELTA),
    "VsTarget": ("Sales vs target", "(SUM([sales_pence]) - SUM([target_pence])) / SUM([target_pence])", DELTA),
    "Margin": ("Gross margin", "SUM([profit_pence]) / SUM([sales_pence])", PERCENT),
    "Stores": ("Stores", "COUNTD([store])", "#,##0"),
    "PerStore": ("Net sales per store", "SUM([sales_pence]) / 100 / COUNTD([store])", GBP),
    "Units": ("Units sold", "SUM([units])", "#,##0"),
    "PromoShare": ("Promo sales share", "SUM([promo_pence]) / SUM([sales_pence])", PERCENT),
}
COLORS = {
    "NetSales": BLUE, "AnnualChange": TEAL, "VsTarget": ORANGE, "Margin": PURPLE,
    "Stores": BLUE, "PerStore": TEAL, "Units": TEAL, "PromoShare": ORANGE,
}
PAGES = [
    {
        "name": "Retailer performance", "accent": BLUE, "description": DISCLAIMER,
        "note": "Select a retailer bar to filter the KPIs and weekly trend. Press Esc to clear.",
        "cards": [("Net sales", "NetSales"), ("Sales vs prior year", "AnnualChange"),
                  ("Sales vs target", "VsTarget"), ("Gross margin", "Margin")],
        "charts": [
            ("Weekly net sales", "NetSales", None, "week", (1400, 39000, 60500, 58300)),
            ("Net sales by retailer", "NetSales", "retailer", None, (63400, 39000, 35200, 58300)),
        ],
        "selectors": {"Net sales by retailer": "retailer"},
    },
    {
        "name": "Store network", "accent": TEAL, "description": DISCLAIMER,
        "note": "Select a retailer or region to inspect its branches. Press Esc to clear.",
        "cards": [("Stores", "Stores"), ("Store network sales", "NetSales"),
                  ("Net sales per store", "PerStore"), ("Store vs target", "VsTarget")],
        "charts": [
            ("Net sales by store", "NetSales", "store", None, (1400, 39000, 58300, 58300)),
            ("Retailer sales", "NetSales", "retailer", None, (61200, 39000, 37400, 27600)),
            ("Target variance by region", "VsTarget", "region", None, (61200, 68300, 37400, 29000)),
        ],
        "selectors": {"Retailer sales": "retailer", "Target variance by region": "region"},
    },
    {
        "name": "Category performance", "accent": PURPLE, "description": DISCLAIMER,
        "note": "Select a retailer or category to filter sales, margin and promotion metrics.",
        "cards": [("Category sales", "NetSales"), ("Units sold", "Units"),
                  ("Category margin", "Margin"), ("Promo sales share", "PromoShare")],
        "charts": [
            ("Net sales by category", "NetSales", "category", None, (1400, 39000, 55600, 58300)),
            ("Category sales by retailer", "NetSales", "retailer", None, (58500, 39000, 40100, 27600)),
            ("Promo share by category", "PromoShare", "category", None, (58500, 68300, 40100, 29000)),
        ],
        "selectors": {"Category sales by retailer": "retailer", "Net sales by category": "category"},
    },
]


def build_extract(path):
    from tableauhyperapi import Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition, TableName, Telemetry

    types = {"date": SqlType.date(), "string": SqlType.text(), "integer": SqlType.big_int()}
    assert tuple(FIELDS) == INPUT_COLUMNS
    table = TableDefinition(TableName("Extract", "Extract"), [
        TableDefinition.Column(key, types[dtype]) for key, (dtype, _) in FIELDS.items()
    ])
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(DATA)}) as hyper:
        with Connection(hyper.endpoint, path, CreateMode.CREATE_AND_REPLACE) as connection:
            connection.catalog.create_schema("Extract")
            connection.catalog.create_table(table)
            with Inserter(connection, table) as insert:
                insert.add_rows((date.fromisoformat(week), *rest) for week, *rest in sales_rows())
                insert.execute()
            return connection.execute_list_query("""
                SELECT COUNT(*), COUNT(DISTINCT "store"), COUNT(DISTINCT "week"), SUM("sales_pence")
                FROM "Extract"."Extract"
            """)[0]


def package(hyper):
    workbook = DATA / f"{TITLE}.twb"
    build_workbook(workbook, FIELDS, METRICS, COLORS, PAGES, "hyper.fmcg", "Simulated FMCG sales",
                   EXTRACT, dashboard_size=(1150, 730))
    with ZipFile(OUTPUT / f"{TITLE}.twbx", "w", ZIP_DEFLATED) as package:
        package.write(workbook, workbook.name)
        package.write(hyper, EXTRACT)


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hyper = DATA / "simulated_fmcg.hyper"
    print("Rows, stores, weeks, net sales in pence", build_extract(hyper))
    package(hyper)
