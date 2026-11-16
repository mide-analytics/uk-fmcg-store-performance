"""Write native Power BI report definitions."""

import json
from hashlib import sha256

from report_design import CANVAS, INK, NAVY, WHITE

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"


def save(path, value, schema=None):
    if schema:
        value = {"$schema": f"{SCHEMA}/{schema}/schema.json", **value}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def measure(name, expression, fmt="#,0"):
    return {"name": name, "expression": expression, "formatString": fmt}


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def fill(color):
    return {"solid": {"color": literal(f"'{color}'")}}


def background(color, page=False):
    properties = {"color": fill(color), "transparency": literal("0D")}
    if not page:
        properties["show"] = literal("true")
    return [{"properties": properties}]


def field(entity, property_name, kind="Column"):
    return {
        "field": {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": property_name}},
        "queryRef": f"{entity}.{property_name}",
        "nativeQueryRef": property_name,
    }


class Page:
    def __init__(self, title, subtitle, accent, definition):
        self.name = self.key(title)
        self.directory = definition / "pages" / self.name
        self.order = 0
        save(self.directory / "page.json", {
            "name": self.name, "displayName": title, "displayOption": "FitToPage",
            "width": 1280, "height": 720,
            "objects": {"background": background(CANVAS, page=True)},
        }, "item/report/definition/page/2.3.1")
        self.text("Page heading", (24, 18, 1232, 83), [
            (title, "27pt", WHITE), (subtitle, "11pt", "#D9E7F7"),
        ], NAVY)
        self.text("Header accent", (24, 101, 1232, 5), [], accent)

    @staticmethod
    def key(value):
        return sha256(value.encode()).hexdigest()[:20]

    def visual(self, title, box, visual_type, roles=None, objects=None, sort=None, color=WHITE, show_title=True):
        self.order += 1000
        x, y, width, height = box
        name = self.key(title)
        visual = {"visualType": visual_type, "visualContainerObjects": {"background": background(color)}}
        if visual_type != "textbox":
            visual["visualContainerObjects"]["title"] = [{"properties": {
                "show": literal("true" if show_title else "false"), "text": literal(f"'{title}'"),
                "fontColor": fill(INK), "fontSize": literal("13D"), "bold": literal("true"),
            }}]
            visual["drillFilterOtherVisuals"] = True
        if objects:
            visual["objects"] = objects
        if roles:
            visual["query"] = {"queryState": {role: {"projections": projections} for role, projections in roles.items()}}
        if sort:
            projection, direction = sort
            visual["query"]["sortDefinition"] = {"sort": [{"field": projection["field"], "direction": direction}]}
        save(self.directory / "visuals" / name / "visual.json", {
            "name": name, "position": {"x": x, "y": y, "width": width, "height": height,
                                       "z": self.order, "tabOrder": self.order},
            "visual": visual,
        }, "item/report/definition/visualContainer/2.14.0")

    def text(self, title, box, lines, color=CANVAS):
        paragraphs = [{"textRuns": [{"value": text, "textStyle": {"fontSize": size, "color": color}}]}
                      for text, size, color in lines]
        self.visual(title, box, "textbox", objects={"general": [{"properties": {"paragraphs": paragraphs}}]}, color=color)

    def cards(self, measures):
        width = (1232 - (len(measures) - 1) * 16) / len(measures)
        for index, (entity, metric, accent, tint) in enumerate(measures):
            self.visual(metric, (24 + (width + 16) * index, 122, width, 106), "card",
                        {"Values": [field(entity, metric, "Measure")]},
                        objects={
                            "labels": [{"properties": {"fontSize": literal("25D"), "color": fill(accent),
                                                       "labelDisplayUnits": literal("1D")}}],
                            "categoryLabels": [{"properties": {"show": literal("false")}}],
                        }, color=tint)

    def chart(self, title, box, visual_type, category, metric, color):
        objects = {"dataPoint": [{"properties": {"fill": fill(color)}}]}
        if visual_type == "lineChart":
            objects["lineStyles"] = [{"properties": {
                "lineChartType": literal("'linear'"), "strokeWidth": literal("3D"),
            }}]
        else:
            objects["labels"] = [{"properties": {"show": literal("true"), "color": fill(INK)}}]
        self.visual(title, box, visual_type, {"Category": [category], "Y": [metric]},
                    objects=objects, sort=(category, "Ascending") if visual_type == "lineChart" else (metric, "Descending"))


def write_report_shell(output, name):
    report = output / f"{name}.Report"
    model = output / f"{name}.SemanticModel"
    definition = report / "definition"
    save(output / f"{name}.pbip", {
        "version": "1.0", "artifacts": [{"report": {"path": report.name}}],
        "settings": {"enableAutoRecovery": True},
    }, "pbip/pbipProperties/1.0.0")
    save(report / "definition.pbir", {
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{model.name}"}},
    }, "item/report/definitionProperties/2.0.0")
    save(definition / "version.json", {"version": "2.0.0"}, "item/report/definition/versionMetadata/1.0.0")
    theme = "Fluent2-CY26SU10"
    save(definition / "report.json", {
        "themeCollection": {"baseTheme": {
            "name": theme, "type": "SharedResources",
            "reportVersionAtImport": {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"},
        }},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": theme, "path": f"BaseThemes/{theme}.json", "type": "BaseTheme"}]}],
    }, "item/report/definition/report/3.3.0")
    return definition, model
