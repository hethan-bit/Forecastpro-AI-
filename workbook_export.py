"""Five-sheet in-memory Excel export for Streamlit's download button."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def build_workbook(
    account: str,
    campaign: str,
    generated_at: str,
    forecast_ranges: list[Any],
    chart_ranges: list[Any],
    historical: list[dict[str, Any]],
) -> bytes:
    try:
        import xlsxwriter
    except ModuleNotFoundError:
        return _build_polished_standard_library_workbook(
            account, campaign, generated_at, forecast_ranges, chart_ranges, historical
        )
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    styles = _styles(workbook)
    _projections(workbook, styles, account, campaign, generated_at, forecast_ranges)
    _history(workbook, styles, historical)
    _graphs(workbook, styles, chart_ranges)
    _outcome_charts(workbook, styles, chart_ranges)
    _recommendations(workbook, styles, chart_ranges)
    workbook.close()
    return output.getvalue()


def _styles(workbook):
    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#123B63",
                "font_size": 16,
                "align": "center",
            }
        ),
        "subtitle": workbook.add_format({"italic": True, "font_color": "#4F6478"}),
        "header": workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#0A7E8C",
                "align": "center",
                "text_wrap": True,
            }
        ),
        "money": workbook.add_format({"num_format": "$#,##0"}),
        "integer": workbook.add_format({"num_format": "#,##0"}),
        "decimal": workbook.add_format({"num_format": "0.000"}),
        "bold": workbook.add_format({"bold": True}),
        "wrap": workbook.add_format({"text_wrap": True, "valign": "top"}),
    }


def _heading(sheet, styles, title, subtitle, columns):
    sheet.merge_range(0, 0, 0, columns - 1, title, styles["title"])
    sheet.merge_range(1, 0, 1, columns - 1, subtitle, styles["subtitle"])
    sheet.hide_gridlines(2)


def _projections(workbook, styles, account, campaign, generated_at, ranges):
    sheet = workbook.add_worksheet("Projections")
    _heading(
        sheet,
        styles,
        "ForecastPro AI — Projections",
        f"{account} | {campaign} | {generated_at}",
        12,
    )
    headers = [
        "Tier",
        "Investment",
        "Delivered",
        "Prospects",
        "Customers Min",
        "Customers Max",
        "Revenue Min",
        "Revenue Max",
        "CPIx Min",
        "CPIx Max",
        "iROAS Min",
        "iROAS Max",
    ]
    sheet.write_row(3, 0, headers, styles["header"])
    for index, row in enumerate(ranges, 4):
        sheet.write_row(
            index,
            0,
            [
                row.tier_label,
                float(row.investment),
                float(row.delivered_volume),
                float(row.prospects),
                float(row.incremental_customers.minimum),
                float(row.incremental_customers.maximum),
                float(row.incremental_revenue.minimum),
                float(row.incremental_revenue.maximum),
                float(row.cpix.minimum),
                float(row.cpix.maximum),
                float(row.iroas.minimum),
                float(row.iroas.maximum),
            ],
        )
    sheet.set_column("A:A", 28)
    sheet.set_column("B:L", 16)
    sheet.set_column("B:B", 16, styles["money"])
    sheet.set_column("C:F", 16, styles["integer"])
    sheet.set_column("G:J", 16, styles["money"])
    sheet.set_column("K:L", 16, styles["decimal"])
    sheet.freeze_panes(4, 0)
    sheet.autofilter(3, 0, 3 + len(ranges), 11)


def _history(workbook, styles, rows):
    sheet = workbook.add_worksheet("Historic Data")
    _heading(
        sheet,
        styles,
        "ForecastPro AI — Historic Data",
        "Selected reconciled Snowflake quarterly snapshots",
        12,
    )
    headers = [
        "Quarter",
        "Status",
        "Final Week",
        "Delivered",
        "Spend",
        "Historical CPM",
        "Prospects",
        "Inc. Customers",
        "Inc. Revenue",
        "CPIx",
        "iROAS",
        "Frequency",
    ]
    sheet.write_row(3, 0, headers, styles["header"])
    for index, row in enumerate(rows, 4):
        sheet.write_row(
            index,
            0,
            [
                row["campaign_quarter"],
                "Complete" if row["is_complete"] else "Partial",
                row["source_week_order"],
                row["delivered_volume"],
                float(row["source_spend"]),
                float(row["historical_cpm"]),
                row["prospects"],
                float(row["incremental_customers"]),
                float(row["incremental_revenue"]),
                float(row["cpix"]),
                float(row["iroas"]),
                float(row["frequency"]),
            ],
        )
    sheet.set_column("A:L", 16)
    sheet.set_column("D:D", 16, styles["integer"])
    sheet.set_column("E:F", 16, styles["money"])
    sheet.set_column("G:H", 16, styles["integer"])
    sheet.set_column("I:J", 16, styles["money"])
    sheet.set_column("K:L", 16, styles["decimal"])
    sheet.freeze_panes(4, 0)
    sheet.autofilter(3, 0, 3 + len(rows), 11)


def _graphs(workbook, styles, rows):
    sheet = workbook.add_worksheet("Graphs")
    _heading(
        sheet,
        styles,
        "ForecastPro AI — Graphs",
        "Cost and return trend by investment tier",
        4,
    )
    sheet.write_row(
        3,
        0,
        ["Tier", "Investment", "CPIx midpoint", "iROAS midpoint"],
        styles["header"],
    )
    for index, row in enumerate(rows, 4):
        sheet.write_row(
            index,
            0,
            [row.tier_label, float(row.investment), _mid(row.cpix), _mid(row.iroas)],
        )
    sheet.set_column("A:A", 28)
    sheet.set_column("B:C", 16, styles["money"])
    sheet.set_column("D:D", 16, styles["decimal"])
    last = 3 + len(rows)
    for column, title, position in (
        (2, "CPIx rises with investment", "F4"),
        (3, "iROAS declines with investment", "F21"),
    ):
        chart = workbook.add_chart({"type": "line"})
        chart.add_series(
            {
                "name": title,
                "categories": ["Graphs", 4, 0, last, 0],
                "values": ["Graphs", 4, column, last, column],
                "marker": {"type": "circle"},
            }
        )
        chart.set_title({"name": title})
        chart.set_legend({"none": True})
        sheet.insert_chart(position, chart, {"x_scale": 1.35, "y_scale": 1.05})


def _outcome_charts(workbook, styles, rows):
    sheet = workbook.add_worksheet("Charts")
    _heading(
        sheet,
        styles,
        "ForecastPro AI — Charts",
        "Forecast outcomes by investment tier",
        3,
    )
    sheet.write_row(
        3,
        0,
        ["Tier", "Incremental Customers midpoint", "Incremental Revenue midpoint"],
        styles["header"],
    )
    for index, row in enumerate(rows, 4):
        sheet.write_row(
            index,
            0,
            [
                row.tier_label,
                _mid(row.incremental_customers),
                _mid(row.incremental_revenue),
            ],
        )
    sheet.set_column("A:A", 28)
    sheet.set_column("B:B", 22, styles["integer"])
    sheet.set_column("C:C", 22, styles["money"])
    last = 3 + len(rows)
    for column, title, position in (
        (1, "Incremental customers by tier", "E4"),
        (2, "Incremental revenue by tier", "E21"),
    ):
        chart = workbook.add_chart({"type": "column"})
        chart.add_series(
            {
                "name": title,
                "categories": ["Charts", 4, 0, last, 0],
                "values": ["Charts", 4, column, last, column],
            }
        )
        chart.set_title({"name": title})
        chart.set_legend({"none": True})
        sheet.insert_chart(position, chart, {"x_scale": 1.35, "y_scale": 1.05})


def _recommendations(workbook, styles, rows):
    sheet = workbook.add_worksheet("Recommendations")
    _heading(
        sheet,
        styles,
        "ForecastPro AI — Recommendations",
        "Automated recommendations based on the calculated forecast pattern",
        2,
    )
    sheet.write_row(3, 0, ["Recommendation", "Rationale"], styles["header"])
    cpix_start, cpix_end = _mid(rows[0].cpix), _mid(rows[-1].cpix)
    iroas_start, iroas_end = _mid(rows[0].iroas), _mid(rows[-1].iroas)
    content = [
        (
            "Use the tier table as the approval point",
            "Investment tiers are anchored to the current budget and Sustainable Scale.",
        ),
        (
            "Expect diminishing marginal efficiency",
            f"CPIx changes from {cpix_start:.2f} to {cpix_end:.2f} while iROAS changes from {iroas_start:.3f} to {iroas_end:.3f}.",
        ),
        (
            "Review marginal metrics before moving up a tier",
            "Marginal CPIx and Marginal iROAS isolate the additional budget between adjacent tiers.",
        ),
        (
            "Keep improvement scenarios documented",
            "Use improvement factors only for evidence-backed operational changes.",
        ),
    ]
    for index, (recommendation, rationale) in enumerate(content, 4):
        sheet.write(index, 0, recommendation, styles["bold"])
        sheet.write(index, 1, rationale, styles["wrap"])
    sheet.set_column("A:A", 38)
    sheet.set_column("B:B", 70)


def _mid(value_range) -> float:
    return float((value_range.minimum + value_range.maximum) / 2)


def _build_standard_library_workbook(
    account: str,
    campaign: str,
    generated_at: str,
    forecast_ranges: list[Any],
    chart_ranges: list[Any],
    historical: list[dict[str, Any]],
) -> bytes:
    """Create a dependency-free XLSX for Workspace accounts without PyPI egress."""

    projection_rows = [
        [
            "Tier",
            "Investment",
            "Delivered",
            "Prospects",
            "Customers Min",
            "Customers Max",
            "Revenue Min",
            "Revenue Max",
            "CPIx Min",
            "CPIx Max",
            "iROAS Min",
            "iROAS Max",
        ]
    ] + [
        [
            row.tier_label,
            row.investment,
            row.delivered_volume,
            row.prospects,
            row.incremental_customers.minimum,
            row.incremental_customers.maximum,
            row.incremental_revenue.minimum,
            row.incremental_revenue.maximum,
            row.cpix.minimum,
            row.cpix.maximum,
            row.iroas.minimum,
            row.iroas.maximum,
        ]
        for row in forecast_ranges
    ]
    history_rows = [
        [
            "Quarter",
            "Status",
            "Final Week",
            "Delivered",
            "Spend",
            "Historical CPM",
            "Prospects",
            "Inc. Customers",
            "Inc. Revenue",
            "CPIx",
            "iROAS",
            "Frequency",
        ]
    ] + [
        [
            row["campaign_quarter"],
            "Complete" if row["is_complete"] else "Partial",
            row["source_week_order"],
            row["delivered_volume"],
            row["source_spend"],
            row["historical_cpm"],
            row["prospects"],
            row["incremental_customers"],
            row["incremental_revenue"],
            row["cpix"],
            row["iroas"],
            row["frequency"],
        ]
        for row in historical
    ]
    graph_rows = [["Tier", "Investment", "CPIx midpoint", "iROAS midpoint"]] + [
        [row.tier_label, row.investment, _mid(row.cpix), _mid(row.iroas)]
        for row in chart_ranges
    ]
    chart_rows = [
        ["Tier", "Incremental Customers midpoint", "Incremental Revenue midpoint"]
    ] + [
        [row.tier_label, _mid(row.incremental_customers), _mid(row.incremental_revenue)]
        for row in chart_ranges
    ]
    first, last = chart_ranges[0], chart_ranges[-1]
    recommendation_rows = [
        ["Recommendation", "Rationale"],
        [
            "Use the tier table as the approval point",
            "Investment tiers are anchored to the current budget and Sustainable Scale.",
        ],
        [
            "Expect diminishing marginal efficiency",
            f"CPIx changes from {_mid(first.cpix):.2f} to {_mid(last.cpix):.2f}; iROAS changes from {_mid(first.iroas):.3f} to {_mid(last.iroas):.3f}.",
        ],
        [
            "Review marginal metrics before moving up a tier",
            "Marginal metrics isolate the performance of additional budget.",
        ],
        [
            "Keep improvement scenarios documented",
            "Use improvement factors only for evidence-backed changes.",
        ],
    ]
    sheets = [
        (
            "Projections",
            [
                ["ForecastPro AI — Projections"],
                [f"{account} | {campaign} | {generated_at}"],
                [],
            ]
            + projection_rows,
        ),
        (
            "Historic Data",
            [
                ["ForecastPro AI — Historic Data"],
                ["Selected reconciled Snowflake quarterly snapshots"],
                [],
            ]
            + history_rows,
        ),
        (
            "Graphs",
            [
                ["ForecastPro AI — Graphs"],
                ["Cost and return trend by investment tier"],
                [],
            ]
            + graph_rows,
        ),
        (
            "Charts",
            [["ForecastPro AI — Charts"], ["Forecast outcomes by investment tier"], []]
            + chart_rows,
        ),
        (
            "Recommendations",
            [["ForecastPro AI — Recommendations"], ["Automated recommendations"], []]
            + recommendation_rows,
        ),
    ]
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
        archive.writestr("_rels/.rels", _root_relationships())
        archive.writestr("xl/workbook.xml", _workbook_xml([name for name, _ in sheets]))
        archive.writestr(
            "xl/_rels/workbook.xml.rels", _workbook_relationships(len(sheets))
        )
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (_, rows) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))
    return output.getvalue()


def _worksheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_number, row in enumerate(rows, 1):
        cells = []
        for column_number, value in enumerate(row, 1):
            if value is None:
                continue
            reference = f"{_column_name(column_number)}{row_number}"
            if isinstance(value, (int, float)) or value.__class__.__name__ == "Decimal":
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                text = escape(str(value))
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t>{text}</t></is></c>'
                )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )


def _column_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _content_types(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{sheets}</Types>"
    )


def _root_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(names, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _workbook_relationships(sheet_count: int) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{relationships}<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="1"><xf/></cellXfs>'
        "</styleSheet>"
    )


# Snowflake Workspaces does not always make xlsxwriter importable at runtime.
# This fallback intentionally produces a fully formatted workbook with embedded
# SVG charts instead of degrading to plain, unstyled XML tables.
def _build_polished_standard_library_workbook(
    account: str,
    campaign: str,
    generated_at: str,
    forecast_ranges: list[Any],
    chart_ranges: list[Any],
    historical: list[dict[str, Any]],
) -> bytes:
    projection_rows = [
        [
            "Tier", "Investment", "Delivered", "Prospects", "Inc. Customers — Low",
            "Inc. Customers — High", "Inc. Revenue — Low", "Inc. Revenue — High",
            "CPIx — Low", "CPIx — High", "iROAS — Low", "iROAS — High",
        ]
    ] + [
        [
            row.tier_label, row.investment, row.delivered_volume, row.prospects,
            row.incremental_customers.minimum, row.incremental_customers.maximum,
            row.incremental_revenue.minimum, row.incremental_revenue.maximum,
            row.cpix.minimum, row.cpix.maximum, row.iroas.minimum, row.iroas.maximum,
        ]
        for row in forecast_ranges
    ]
    history_rows = [
        [
            "Quarter", "Status", "Final Week", "Delivered", "Spend", "Historical CPM",
            "Prospects", "Inc. Customers", "Inc. Revenue", "CPIx", "iROAS", "Frequency",
        ]
    ] + [
        [
            row["campaign_quarter"], "Complete" if row["is_complete"] else "Partial",
            row["source_week_order"], row["delivered_volume"], row["source_spend"],
            row["historical_cpm"], row["prospects"], row["incremental_customers"],
            row["incremental_revenue"], row["cpix"], row["iroas"], row["frequency"],
        ]
        for row in historical
    ]
    graph_rows = [["Tier", "Investment", "CPIx", "iROAS"]] + [
        [row.tier_label, row.investment, _mid(row.cpix), _mid(row.iroas)]
        for row in chart_ranges
    ]
    outcome_rows = [["Tier", "Incremental Customers", "Incremental Revenue"]] + [
        [row.tier_label, _mid(row.incremental_customers), _mid(row.incremental_revenue)]
        for row in chart_ranges
    ]
    first, last = chart_ranges[0], chart_ranges[-1]
    recommendation_rows = [
        ["Recommendation", "Rationale"],
        [
            "Use the tier table as the approval point",
            "Investment tiers are anchored to the current budget and Sustainable Scale.",
        ],
        [
            "Expect diminishing marginal efficiency",
            f"CPIx moves from {_mid(first.cpix):.2f} to {_mid(last.cpix):.2f}; "
            f"iROAS moves from {_mid(first.iroas):.2f} to {_mid(last.iroas):.2f}.",
        ],
        [
            "Review marginal metrics before moving up a tier",
            "Marginal CPIx and Marginal iROAS isolate the economics of the next investment step.",
        ],
        [
            "Document improvement scenarios",
            "Use improvement factors only for evidence-backed operational changes.",
        ],
    ]

    sheets = [
        {
            "name": "Projections",
            "title": "ForecastPro AI — Forecast Results",
            "subtitle": f"{account} | {campaign} | Generated {generated_at}",
            "rows": projection_rows,
            "widths": [28, 16, 16, 16, 18, 18, 18, 18, 14, 14, 13, 13],
            "formats": {1: "money", 2: "integer", 3: "integer", 4: "integer", 5: "integer", 6: "money", 7: "money", 8: "money", 9: "money", 10: "decimal", 11: "decimal"},
        },
        {
            "name": "Historic Data",
            "title": "ForecastPro AI — Historical Inputs",
            "subtitle": "Selected reconciled Snowflake quarterly snapshots",
            "rows": history_rows,
            "widths": [14, 12, 11, 16, 15, 15, 16, 16, 16, 14, 12, 12],
            "formats": {2: "integer", 3: "integer", 4: "money", 5: "money", 6: "integer", 7: "integer", 8: "money", 9: "money", 10: "decimal", 11: "decimal"},
        },
        {
            "name": "Graphs",
            "title": "ForecastPro AI — Forecast Economics",
            "subtitle": "CPIx and iROAS trend by investment tier",
            "rows": graph_rows,
            "widths": [28, 16, 15, 13],
            "formats": {1: "money", 2: "money", 3: "decimal"},
            "charts": [
                _line_chart_svg("CPIx trend by investment tier", [str(r[0]) for r in graph_rows[1:]], [float(r[2]) for r in graph_rows[1:]], "#00A7B5", "CPIx"),
                _line_chart_svg("iROAS trend by investment tier", [str(r[0]) for r in graph_rows[1:]], [float(r[3]) for r in graph_rows[1:]], "#6D28D9", "iROAS"),
            ],
        },
        {
            "name": "Charts",
            "title": "ForecastPro AI — Forecast Outcomes",
            "subtitle": "Incremental customers and revenue by investment tier",
            "rows": outcome_rows,
            "widths": [28, 22, 22],
            "formats": {1: "integer", 2: "money"},
            "charts": [
                _column_chart_svg("Incremental customers by tier", [str(r[0]) for r in outcome_rows[1:]], [float(r[1]) for r in outcome_rows[1:]], "#00A7B5", "Customers"),
                _column_chart_svg("Incremental revenue by tier", [str(r[0]) for r in outcome_rows[1:]], [float(r[2]) for r in outcome_rows[1:]], "#123B63", "Revenue"),
            ],
        },
        {
            "name": "Recommendations",
            "title": "ForecastPro AI — Recommendations",
            "subtitle": "Decision guidance from the calculated forecast pattern",
            "rows": recommendation_rows,
            "widths": [42, 88],
            "formats": {0: "recommendation", 1: "wrap"},
            "recommendations": True,
        },
    ]

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        chart_count = sum(len(spec.get("charts", [])) for spec in sheets)
        archive.writestr("[Content_Types].xml", _polished_content_types(len(sheets), chart_count))
        archive.writestr("_rels/.rels", _root_relationships())
        archive.writestr("xl/workbook.xml", _polished_workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships(len(sheets)))
        archive.writestr("xl/styles.xml", _polished_styles_xml())

        media_index = 1
        drawing_index = 1
        for sheet_index, spec in enumerate(sheets, 1):
            chart_media_ids = list(range(media_index, media_index + len(spec.get("charts", []))))
            drawing_id = drawing_index if chart_media_ids else None
            archive.writestr(
                f"xl/worksheets/sheet{sheet_index}.xml",
                _polished_sheet_xml(spec, drawing_id),
            )
            if drawing_id:
                archive.writestr(
                    f"xl/worksheets/_rels/sheet{sheet_index}.xml.rels",
                    _worksheet_drawing_relationship(drawing_id),
                )
                archive.writestr(
                    f"xl/drawings/drawing{drawing_id}.xml",
                    _drawing_xml(chart_media_ids),
                )
                archive.writestr(
                    f"xl/drawings/_rels/drawing{drawing_id}.xml.rels",
                    _drawing_relationships(chart_media_ids),
                )
                for image_id, svg in zip(chart_media_ids, spec["charts"]):
                    archive.writestr(f"xl/media/image{image_id}.svg", svg)
                media_index += len(chart_media_ids)
                drawing_index += 1
    return output.getvalue()


def _polished_sheet_xml(spec: dict[str, Any], drawing_id: int | None) -> str:
    rows = [[spec["title"]], [spec["subtitle"]], [], *spec["rows"]]
    last_col = _column_name(len(spec["rows"][0]))
    last_row = len(rows)
    row_xml = []
    for row_number, row in enumerate(rows, 1):
        cells = []
        for column_number, value in enumerate(row, 1):
            if value is None:
                continue
            style = _polished_cell_style(spec, row_number, column_number - 1)
            cells.append(_polished_cell_xml(row_number, column_number, value, style))
        height = " ht=\"28\" customHeight=\"1\"" if row_number == 1 else ""
        height = " ht=\"22\" customHeight=\"1\"" if row_number == 2 else height
        height = " ht=\"32\" customHeight=\"1\"" if row_number == 4 else height
        if spec.get("recommendations") and row_number >= 5:
            height = " ht=\"44\" customHeight=\"1\""
        row_xml.append(f'<row r="{row_number}"{height}>{"".join(cells)}</row>')
    columns = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(spec["widths"], 1)
    )
    merge_cells = f'<mergeCells count="2"><mergeCell ref="A1:{last_col}1"/><mergeCell ref="A2:{last_col}2"/></mergeCells>'
    pane = '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/>'
    drawing = f'<drawing r:id="rId1"/>' if drawing_id else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
        f'{pane}<selection pane="bottomLeft" activeCell="A5" sqref="A5"/>'
        '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="18"/>'
        f'<cols>{columns}</cols><sheetData>{"".join(row_xml)}</sheetData>{merge_cells}'
        f'<autoFilter ref="A4:{last_col}{last_row}"/>{drawing}'
        '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        '</worksheet>'
    )


def _polished_cell_style(spec: dict[str, Any], row_number: int, column: int) -> int:
    if row_number == 1:
        return 1
    if row_number == 2:
        return 2
    if row_number == 4:
        return 3
    if spec.get("recommendations") and row_number >= 5:
        return 10 if column == 0 else 11
    style = spec.get("formats", {}).get(column, "text")
    return {"text": 4, "money": 5, "integer": 6, "decimal": 7, "percent": 8, "wrap": 9}.get(style, 4)


def _polished_cell_xml(row: int, column: int, value: Any, style: int) -> str:
    reference = f"{_column_name(column)}{row}"
    if isinstance(value, (int, float)) or value.__class__.__name__ == "Decimal":
        return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'
    text = escape(str(value))
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{reference}" s="{style}" t="inlineStr"><is><t{preserve}>{text}</t></is></c>'


def _polished_workbook_xml(sheets: list[dict[str, Any]]) -> str:
    items = "".join(
        f'<sheet name="{escape(spec["name"])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, spec in enumerate(sheets, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<bookViews><workbookView activeTab="0"/></bookViews>'
        f'<sheets>{items}</sheets></workbook>'
    )


def _polished_content_types(sheet_count: int, image_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    drawings = "".join(
        f'<Override PartName="/xl/drawings/drawing{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
        for i in range(1, image_count // 2 + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="svg" ContentType="image/svg+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{sheets}{drawings}</Types>'
    )


def _worksheet_drawing_relationship(drawing_id: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing{drawing_id}.xml"/>'
        '</Relationships>'
    )


def _drawing_relationships(image_ids: list[int]) -> str:
    entries = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{image_id}.svg"/>'
        for index, image_id in enumerate(image_ids, 1)
    )
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + entries + '</Relationships>'


def _drawing_xml(image_ids: list[int]) -> str:
    anchors = []
    for index, _ in enumerate(image_ids, 1):
        start_row = 3 + (index - 1) * 18
        end_row = start_row + 15
        anchors.append(
            '<xdr:twoCellAnchor editAs="oneCell">'
            f'<xdr:from><xdr:col>5</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{start_row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            f'<xdr:to><xdr:col>15</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{end_row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
            f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{index}" name="Forecast chart {index}"/><xdr:cNvPicPr/></xdr:nvPicPr>'
            f'<xdr:blipFill><a:blip r:embed="rId{index}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
            '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>'
            '<xdr:clientData/></xdr:twoCellAnchor>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'{"".join(anchors)}</xdr:wsDr>'
    )


def _polished_styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="3"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0"/><numFmt numFmtId="165" formatCode="#\u002C##0"/><numFmt numFmtId="166" formatCode="0.00"/></numFmts>'
        '<fonts count="5"><font><sz val="10"/><color rgb="FF102A43"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><i/><sz val="10"/><color rgb="FF4F6478"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FF102A43"/><name val="Calibri"/></font></fonts>'
        '<fills count="6"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF123B63"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0A7E8C"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF4F8FB"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF3C4"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="2"><border><left/><right/><top/><bottom/></border><border><left style="thin"><color rgb="FFD7E3EC"/></left><right style="thin"><color rgb="FFD7E3EC"/></right><top style="thin"><color rgb="FFD7E3EC"/></top><bottom style="thin"><color rgb="FFD7E3EC"/></bottom></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="12">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment horizontal="center" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="10" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="4" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>'
        '</cellXfs></styleSheet>'
    )


def _line_chart_svg(title: str, labels: list[str], values: list[float], color: str, unit: str) -> str:
    return _chart_svg(title, labels, values, color, unit, "line")


def _column_chart_svg(title: str, labels: list[str], values: list[float], color: str, unit: str) -> str:
    return _chart_svg(title, labels, values, color, unit, "column")


def _chart_svg(title: str, labels: list[str], values: list[float], color: str, unit: str, chart_type: str) -> str:
    width, height, left, top, right, bottom = 900, 360, 72, 54, 28, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    low, high = min(values or [0]), max(values or [1])
    span = max(high - low, 1)
    low = max(0, low - span * 0.12)
    high += span * 0.12
    scale = max(high - low, 1)
    grid = []
    for tick in range(5):
        y = top + plot_h - (tick / 4) * plot_h
        value = low + (tick / 4) * scale
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#D7E3EC" stroke-width="1"/>')
        grid.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="#4F6478">{escape(_compact_chart_number(value, unit))}</text>')
    points = []
    bars = []
    ticks = []
    for index, value in enumerate(values):
        x = left + ((index + 0.5) / max(len(values), 1)) * plot_w
        y = top + plot_h - ((value - low) / scale) * plot_h
        label = escape(_compact_tier_label(labels[index]))
        ticks.append(f'<text x="{x:.1f}" y="{height-42}" text-anchor="end" transform="rotate(-32 {x:.1f} {height-42})" font-size="10" fill="#4F6478">{label}</text>')
        if chart_type == "line":
            points.append((x, y))
        else:
            bar_w = plot_w / max(len(values), 1) * 0.54
            bars.append(f'<rect x="{x-bar_w/2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{top+plot_h-y:.1f}" rx="3" fill="{color}"/>')
    if chart_type == "line":
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        visual = f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>' + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="white" stroke="{color}" stroke-width="3"/>' for x, y in points)
    else:
        visual = "".join(bars)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#FFFFFF"/>'
        f'<text x="{left}" y="30" font-family="Calibri,Arial,sans-serif" font-size="20" font-weight="700" fill="#123B63">{escape(title)}</text>'
        f'<text x="{left}" y="47" font-family="Calibri,Arial,sans-serif" font-size="11" fill="#4F6478">ForecastPro AI • {escape(unit)} by investment tier</text>'
        f'{"".join(grid)}{visual}{"".join(ticks)}'
        '</svg>'
    )


def _compact_tier_label(value: str) -> str:
    replacements = {
        "Sustainable Scale": "Sustainable",
        "Incremental Reach ": "Inc. ",
        "Maximum Scale ": "Max ",
        "Accelerated Growth": "Accelerated",
        "Breakout Growth": "Breakout",
        "Steady Growth": "Steady",
        "Core Growth": "Core",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value[:18]


def _compact_chart_number(value: float, unit: str) -> str:
    prefix = "$" if unit in {"CPIx", "Revenue"} else ""
    if abs(value) >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{prefix}{value / 1_000:.1f}K"
    return f"{prefix}{value:.1f}"
