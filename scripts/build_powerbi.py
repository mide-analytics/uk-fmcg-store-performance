"""Build the FMCG Power BI project with embedded simulated weekly data."""

import base64
import json
import zlib
from uuid import NAMESPACE_URL, uuid5

from powerbi_report import Page, field, literal, measure, save, write_report_shell
from fmcg_data import DISCLAIMER, FIELDS, ROOT, TITLE, sales_rows
from report_design import BLUE, ORANGE, PURPLE, TEAL

OUTPUT = ROOT / "powerbi"
TABLE = "Weekly Sales"
PALETTE = {
    BLUE: "#E2ECFF", ORANGE: "#FCEBDD", TEAL: "#DFF4EF", PURPLE: "#EFE5FC",
}


def label(name):
    return name.replace("_", " ").title()


def build_model(model):
    payload = json.dumps(list(sales_rows()), ensure_ascii=False, separators=(",", ":")).encode()
    compressor = zlib.compressobj(level=9, wbits=-15)
    encoded = base64.b64encode(compressor.compress(payload) + compressor.flush()).decode("ascii")
    chunks = " &\n        ".join(f'"{encoded[i:i + 4096]}"' for i in range(0, len(encoded), 4096))
    columns = []
    transforms = []
    for index, name in enumerate(FIELDS):
        dtype, mtype = ("int64", "Int64.Type") if index >= 6 else ("string", "type text")
        if name == "week":
            dtype, mtype = "dateTime", "type date"
        columns.append({
            "name": label(name), "sourceColumn": name, "dataType": dtype, "summarizeBy": "none",
            "isHidden": index >= 6,
            "lineageTag": str(uuid5(NAMESPACE_URL, f"{TITLE}/{name}")),
            **({"formatString": "dd MMM yyyy"} if name == "week" else {}),
        })
        transforms.append(f'{{"{name}", {mtype}}}')
    names = ", ".join(json.dumps(name) for name in FIELDS)
    gbp = "£#,0;−£#,0"
    signed = "+0.0%;−0.0%;0.0%"
    metrics = [
        measure("Net sales", f"SUM('{TABLE}'[Sales Pence]) / 100", gbp),
        measure("Prior-year sales", f"SUM('{TABLE}'[Prior Sales Pence]) / 100", gbp),
        measure("Sales target", f"SUM('{TABLE}'[Target Pence]) / 100", gbp),
        measure("Sales vs prior year", "DIVIDE([Net sales] - [Prior-year sales], [Prior-year sales])", signed),
        measure("Sales vs target", "DIVIDE([Net sales] - [Sales target], [Sales target])", signed),
        measure("Gross margin", f"DIVIDE(SUM('{TABLE}'[Profit Pence]), SUM('{TABLE}'[Sales Pence]))", "0.0%"),
        measure("Units sold", f"SUM('{TABLE}'[Units])"),
        measure("Promo sales share", f"DIVIDE(SUM('{TABLE}'[Promo Pence]), SUM('{TABLE}'[Sales Pence]))", "0.0%"),
        measure("Stores", f"DISTINCTCOUNT('{TABLE}'[Store])"),
        measure("Net sales per store", "DIVIDE([Net sales], [Stores])", gbp),
    ]
    save(model / "model.bim", {
        "name": TITLE, "compatibilityLevel": 1600,
        "model": {
            "culture": "en-GB", "sourceQueryCulture": "en-GB",
            "defaultPowerBIDataSourceVersion": "powerBI_V3", "discourageImplicitMeasures": True,
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps([TABLE])},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
            "tables": [{
                "name": TABLE, "columns": columns, "measures": metrics,
                "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
                "partitions": [{"name": TABLE, "mode": "import", "source": {
                    "type": "m", "expression": [
                        "let", f"    Encoded = {chunks},",
                        "    Rows = Json.Document(Binary.Decompress(Binary.FromText(Encoded, BinaryEncoding.Base64), Compression.Deflate)),",
                        f"    Weekly = Table.FromRows(Rows, {{{names}}})",
                        f'in Table.TransformColumnTypes(Weekly, {{{", ".join(transforms)}}}, "en-GB")',
                    ],
                }}],
            }],
        },
    })
    save(model / "definition.pbism", {"version": "4.0", "settings": {}},
         "item/semanticModel/definitionProperties/1.0.0")


def build_report(definition):
    def metric(name):
        return field(TABLE, name, "Measure")

    def cards(page, *items):
        page.cards([(TABLE, name, color, PALETTE[color]) for name, color in items])

    def filter_by(page, name, x, width=297):
        page.visual(name, (x, 243, width, 78), "slicer",
                    {"Values": [field(TABLE, name)]},
                    objects={"data": [{"properties": {"mode": literal("'Dropdown'")}}]}, show_title=False)

    def chart(page, title, box, kind, category, value, color):
        page.chart(title, box, kind, field(TABLE, category), metric(value), color)

    executive = Page("Retailer performance", DISCLAIMER, BLUE, definition)
    cards(executive, ("Net sales", BLUE), ("Sales vs prior year", TEAL),
          ("Sales vs target", ORANGE), ("Gross margin", PURPLE))
    filter_by(executive, "Retailer", 24)
    filter_by(executive, "Region", 337)
    executive.visual("Weekly sales and target", (24, 326, 744, 370), "lineChart",
                     {"Category": [field(TABLE, "Week")],
                      "Y": [metric("Net sales"), metric("Sales target")]},
                     objects={"lineStyles": [{"properties": {"lineChartType": literal("'linear'")}}]},
                     sort=(field(TABLE, "Week"), "Ascending"))
    chart(executive, "Net sales by retailer", (784, 326, 472, 370), "barChart", "Retailer", "Net sales", BLUE)

    stores = Page("Store network", DISCLAIMER, TEAL, definition)
    cards(stores, ("Stores", BLUE), ("Net sales", TEAL), ("Net sales per store", PURPLE), ("Sales vs target", ORANGE))
    for name, x in zip(("Retailer", "Region", "Format"), (24, 337, 650), strict=True):
        filter_by(stores, name, x)
    chart(stores, "Store sales ranking", (24, 326, 752, 370), "barChart", "Store", "Net sales", BLUE)
    chart(stores, "Target variance by region", (792, 326, 464, 370), "barChart", "Region", "Sales vs target", TEAL)

    categories = Page("Category performance", DISCLAIMER, PURPLE, definition)
    cards(categories, ("Net sales", BLUE), ("Units sold", TEAL), ("Gross margin", PURPLE), ("Promo sales share", ORANGE))
    for name, x in zip(("Retailer", "Region", "Category"), (24, 337, 650), strict=True):
        filter_by(categories, name, x)
    chart(categories, "Net sales by category", (24, 326, 696, 370), "barChart", "Category", "Net sales", BLUE)
    chart(categories, "Promo sales share by category", (736, 326, 520, 370), "barChart",
          "Category", "Promo sales share", ORANGE)

    save(definition / "pages" / "pages.json", {
        "pageOrder": [page.name for page in (executive, stores, categories)], "activePageName": executive.name,
    }, "item/report/definition/pagesMetadata/1.1.0")


if __name__ == "__main__":
    definition, model = write_report_shell(OUTPUT, TITLE)
    build_model(model)
    build_report(definition)
