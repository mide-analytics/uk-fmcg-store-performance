"""Write native Tableau workbook definitions."""

from uuid import uuid4
from xml.etree import ElementTree as ET

from report_design import BLUE, CANVAS, MUTED, NAVY, ORANGE, PURPLE, TEAL, WHITE

USER = "http://www.tableausoftware.com/xml/user"
TINTS = {BLUE: "#E2ECFF", ORANGE: "#FCEBDD", TEAL: "#DFF4EF", PURPLE: "#EFE5FC"}


def element(parent, tag, **attributes):
    return ET.SubElement(parent, tag, {key.rstrip("_").replace("_", "-"): str(value) for key, value in attributes.items()})


def uid(parent):
    element(parent, "simple-id", uuid="{" + str(uuid4()).upper() + "}")


def define_column(parent, key, fields, metrics):
    if key in metrics:
        caption, formula, fmt = metrics[key]
        column = element(parent, "column", name=f"[{key}]", caption=caption, datatype="real",
                         default_format=fmt, role="measure", type="quantitative")
        element(column, "calculation", class_="tableau", formula=formula)
        return
    dtype, caption = fields[key]
    dimension = dtype in {"string", "date"} or key == "elapsed_month"
    element(parent, "column", name=f"[{key}]", caption=caption, datatype=dtype,
            role="dimension" if dimension else "measure",
            type={"string": "nominal", "date": "ordinal"}.get(dtype, "quantitative"))


def build_workbook(path, fields, metrics, colors, dashboard_specs, source_name, caption, extract,
                   dashboard_size=(1060, 600)):
    ET.register_namespace("user", USER)
    root = ET.Element("workbook", {"original-version": "18.1", "version": "18.1",
                                  "source-build": "2026.3.0 (20263.26.1022.1645)", "source-platform": "win"})
    manifest = element(root, "document-format-change-manifest")
    for feature in ("AccessibleZoneTabOrder", "SheetIdentifierTracking", "WindowsPersistSimpleIdentifiers"):
        element(manifest, feature)
    source = element(element(root, "datasources"), "datasource", name=source_name, caption=caption,
                     inline="true", version="18.1")
    connection = element(source, "connection", class_="hyper", dbname=extract, schema="Extract",
                         tablename="Extract", access_mode="readonly", authentication="auth-none",
                         default_settings="yes", username="tableau_internal_user")
    element(connection, "relation", name="Extract", table="[Extract].[Extract]", type="table")
    metadata = element(connection, "metadata-records")
    remote_types = {"string": 129, "real": 5, "integer": 20, "date": 133}
    for ordinal, (key, (dtype, _)) in enumerate(fields.items()):
        record = element(metadata, "metadata-record", class_="column")
        for tag, value in {
            "remote-name": key, "remote-type": remote_types[dtype], "local-name": f"[{key}]",
            "parent-name": "[Extract]", "remote-alias": key, "ordinal": ordinal, "local-type": dtype,
            "aggregation": {"string": "Count", "date": "Year"}.get(dtype, "Sum"), "contains-null": "true",
        }.items():
            element(record, tag).text = str(value)
    for key in (*fields, *metrics):
        define_column(source, key, fields, metrics)
    if dashboard_specs:
        dimensions = {dimension for spec in dashboard_specs for dimension in spec.get("selectors", {}).values()}
        for dimension in sorted(dimensions):
            action_caption = f"Action ({fields[dimension][1]})"
            group = element(source, "group", caption=action_caption, hidden="true", name=f"[{action_caption}]",
                            name_style="unqualified")
            group.set(f"{{{USER}}}auto-column", "sheet_link")
            element(element(group, "groupfilter", function="crossjoin"), "groupfilter",
                    function="level-members", level=f"[{dimension}]")
        actions = element(root, "actions")
    sheets = element(root, "worksheets")
    dashboards = element(root, "dashboards")
    windows = element(root, "windows", source_height="800")

    def sheet(name, metric, category=None, trend=None, filters=()):
        work = element(sheets, "worksheet", name=name)
        table = element(work, "table")
        view = element(table, "view")
        element(element(view, "datasources"), "datasource", name=source_name, caption=caption)
        deps = element(view, "datasource-dependencies", datasource=source_name)
        for key in (*fields, metric):
            define_column(deps, key, fields, metrics)

        def use(key, suffix, kind):
            measure = key in metrics
            ref = f"[{'usr' if measure else 'none'}:{key}:{suffix}]"
            element(deps, "column-instance", column=f"[{key}]", name=ref, pivot="key", type=kind,
                    derivation="User" if measure else "None")
            return f"[{source_name}].{ref}"

        value = use(metric, "qk", "quantitative")
        category_ref = use(category, "nk", "nominal") if category else None
        month = use(trend, "qk", "quantitative") if trend else None
        filter_refs = []
        for dimension, action_name in filters:
            ref = f"[{source_name}].[Action ({fields[dimension][1]})]"
            clause = element(view, "filter", class_="categorical", column=ref)
            group = element(clause, "groupfilter", function="level-members", level=f"[{dimension}]")
            group.attrib.update({f"{{{USER}}}ui-action-filter": action_name,
                                 f"{{{USER}}}ui-enumeration": "all", f"{{{USER}}}ui-marker": "enumerate"})
            filter_refs.append(ref)
        if month:
            element(view, "filter", class_="quantitative", column=month, included_values="non-null")
            filter_refs.append(month)
        if category_ref:
            element(view, "filter", class_="quantitative", column=value, included_values="non-null")
            filter_refs.append(value)
        if filter_refs:
            slices = element(view, "slices")
            for ref in filter_refs:
                element(slices, "column").text = ref
        element(view, "aggregation", value="true")
        element(table, "style")
        pane = element(element(table, "panes"), "pane", selection_relaxation_option="selection-relaxation-allow")
        element(element(pane, "view"), "breakdown", value="auto")
        mark = "Line" if trend else "Bar" if category else "Text"
        element(pane, "mark", class_=mark)
        if mark == "Text":
            element(element(pane, "encodings"), "text", column=value)
        style = element(element(pane, "style"), "style-rule", element="mark")
        element(style, "format", attr="color", value=colors[metric])
        if mark == "Text":
            element(style, "format", attr="font-size", value="16")
            element(style, "format", attr="mark-labels-show", value="true")
        element(table, "rows").text = value if trend else category_ref
        element(table, "cols").text = month if trend else value if category else None
        uid(work)
        window = element(windows, "window", class_="worksheet", name=name, hidden="true")
        element(window, "cards")
        uid(window)

    def dashboard(name, cards, charts, description, accent, note=None, footer=None, selectors=None):
        selectors = selectors or {}
        action_ids = {}
        for selector, dimension in selectors.items():
            action_name = "[Action_" + uuid4().hex.upper() + "]"
            action_ids[dimension] = action_name
            action = element(actions, "action", caption=f"Filter by {fields[dimension][1]}", name=action_name)
            element(action, "activation", type="on-select", auto_clear="true")
            element(action, "source", dashboard=name, type="sheet", worksheet=selector)
            command = element(action, "command", command="tsc:tsl-filter")
            element(command, "param", name="special-fields", value="all")
            element(command, "param", name="target", value=name)
        board = element(dashboards, "dashboard", name=name, enable_sort_zone_taborder="true")
        element(board, "style")
        width, height = dashboard_size
        element(board, "size", maxheight=height, minheight=height, maxwidth=width, minwidth=width)
        zones = element(element(board, "zones"), "zone", id=4, type_v2="layout-basic", x=0, y=0, w=100000, h=100000)

        def format_zone(zone, color):
            style = element(zone, "zone-style")
            element(style, "format", attr="background-color", value=color)
            element(style, "format", attr="margin", value="0")

        def text_zone(index, box, label, size, color, background, bold=False):
            x, y, width, height = box
            zone = element(zones, "zone", id=index, type_v2="text", x=x, y=y, w=width, h=height)
            run = element(element(zone, "formatted-text"), "run", fontsize=size, fontcolor=color,
                          bold="true" if bold else "false")
            run.text = label
            format_zone(zone, background)

        text_zone(5, (1400, 1800, 97200, 6600), "  " + name, 22, WHITE, NAVY, bold=True)
        text_zone(6, (1400, 8400, 97200, 4300), "   " + description, 10, "#D9E7F7", NAVY)
        text_zone(7, (1400, 12700, 97200, 800), " ", 1, WHITE, accent)
        if note:
            text_zone(8, (1400, 32000 if cards else 15600, 97200, 5200),
                      "   " + note, 11, accent, TINTS[accent], bold=True)
        if footer:
            text_zone(9, (1400, 94500, 97200, 4300), "   " + footer, 10, MUTED, CANVAS)

        win = element(windows, "window", class_="dashboard", name=name)
        viewpoints = element(win, "viewpoints")
        card_width = (97200 - max(0, len(cards) - 1) * 1300) // max(1, len(cards))
        placements = [(title, metric, None, None, (1400 + index * (card_width + 1300), 15500, card_width, 14800))
                      for index, (title, metric) in enumerate(cards)] + charts
        for index, (title, metric, category, trend, (x, y, width, height)) in enumerate(placements, 10):
            sheet(title, metric, category, trend, [
                (dimension, action) for dimension, action in action_ids.items()
                if selectors.get(title) != dimension
            ])
            zone = element(zones, "zone", id=index, name=title, x=x, y=y, w=width, h=height)
            format_zone(zone, WHITE if category or trend else TINTS[colors[metric]])
            viewpoint = element(viewpoints, "viewpoint", name=title)
            if not dashboard_specs or not category:
                element(viewpoint, "zoom", type="entire-view")
        format_zone(zones, CANVAS)
        element(win, "active", id=10)
        uid(win)
        uid(board)

    if dashboard_specs:
        for spec in dashboard_specs:
            dashboard(**spec)

    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
