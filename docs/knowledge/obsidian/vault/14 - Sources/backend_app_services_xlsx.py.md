---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/xlsx.py"
source_hash: "5f5d885e152132e01f8dddee0edc99eca52d898b68971fb587c3bb26f84da220"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/xlsx.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reports_center.py]] - imports
- [[docs_FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md]] - mentioned by docs

```py
"""
Minimal .xlsx writer (2026-10-26, priority G): Office Open XML SpreadsheetML in a zip, standard library only - no
new package or image rebuild. One header sheet ("About": title, source, period, warnings) + one data sheet.
Numbers stay numbers (Excel can sum them); text is written as inline strings; the header row is bold and frozen.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from xml.sax.saxutils import escape

_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheets}
</Types>"""
_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
</styleSheet>"""


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref: str, v, bold: bool = False) -> str:
    st = ' s="1"' if bold else ""
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"{st}><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)) and v == v and v not in (float("inf"), float("-inf")):
        return f'<c r="{ref}"{st}><v>{v}</v></c>'
    if isinstance(v, (datetime, date)):
        v = v.isoformat()
    text = escape(str(v)).replace("\x00", "")
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)       # XML 1.0 legal characters only
    return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{text[:32000]}</t></is></c>'


def _sheet(rows: list[list], freeze: bool) -> str:
    out = []
    for r, row in enumerate(rows):
        cells = "".join(_cell(f"{_col(c)}{r + 1}", v, bold=freeze and r == 0) for c, v in enumerate(row))
        out.append(f'<row r="{r + 1}">{cells}</row>')
    pane = ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
            'state="frozen"/></sheetView></sheetViews>') if freeze and rows else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'{pane}<sheetData>{"".join(out)}</sheetData></worksheet>')


def workbook(sheets: list[tuple[str, list[list], bool]]) -> bytes:
    """sheets: (name, rows, header_row_bold_and_frozen)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        names = [escape(n[:31].replace("/", "-")) for n, _, _ in sheets]
        z.writestr("[Content_Types].xml", _CT.format(sheets="".join(
            f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(sheets)))))
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns='
                   '"http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats'
                   '.org/officeDocument/2006/relationships"><sheets>' + "".join(
                       f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
                       f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                       f'relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
                   + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/'
                   '2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", _STYLES)
        for i, (_, rows, freeze) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sheet(rows, freeze))
    return buf.getvalue()


def report_xlsx(r: dict) -> bytes:
    """A Reports Centre result -> workbook: 'About' (provenance) + 'Data'."""
    about = [["Report", r.get("title")], ["Source", r.get("source")], ["From", r.get("start")], ["To", r.get("end")],
             ["Generated", r.get("generated_at")], ["Rows", r.get("count")]]
    about += [["Warning", w] for w in r.get("warnings") or []]
    cols = r.get("columns") or []
    data = [cols] + [[row.get(c) for c in cols] for row in r.get("rows") or []]
    return workbook([("About", about, False), ("Data", data, True)])

```
