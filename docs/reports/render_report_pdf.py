"""Markdown report -> styled HTML -> PDF (headless Edge/Chrome through the frontend's playwright-core).

    py docs/reports/render_report_pdf.py <report.md> [more.md ...] <out.pdf>

A small converter for the subset the reports use (headings, paragraphs, lists, tables, code blocks, bold, inline
code, links, checkboxes) - no extra Python package needed."""
import html
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def convert(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("    ") and line.strip():                     # indented code block
            block = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                block.append(lines[i][4:])
                i += 1
            out.append("<pre>" + html.escape("\n".join(block).rstrip()) + "</pre>")
            continue
        m = re.match(r"^(#{1,4}) (.*)", line)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|[\s:|-]+\|$", r)]
            t = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append(t + "</tbody></table>")
            continue
        if re.match(r"^\s*([-*]|\d+\.) ", line):
            ordered = bool(re.match(r"^\s*\d+\. ", line))
            items = []
            while i < len(lines) and (re.match(r"^\s*([-*]|\d+\.) ", lines[i]) or
                                      (lines[i].startswith("  ") and lines[i].strip() and items)):
                if re.match(r"^\s*([-*]|\d+\.) ", lines[i]):
                    items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            lis = "".join("<li>" + inline(x).replace("[ ] ", "&#9744; ").replace("[x] ", "&#9745; ") + "</li>" for x in items)
            out.append(f"<{tag}>{lis}</{tag}>")
            continue
        if not line.strip():
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||\s*[-*] |\s*\d+\. |    )", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.2pt; color: #1b2430; line-height: 1.45; }
h1 { font-size: 19pt; color: #0b3b5c; border-bottom: 3px solid #0e7c86; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 13.5pt; color: #0b3b5c; margin-top: 18px; border-bottom: 1px solid #cfd8e3; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #0e5a63; margin-top: 12px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 8.9pt; page-break-inside: auto; }
th { background: #0b3b5c; color: #fff; text-align: left; padding: 4px 6px; }
td { border-bottom: 1px solid #dde4ec; padding: 4px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f8fb; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #eef2f6; padding: 0 3px; border-radius: 3px; }
pre { font-family: Consolas, monospace; font-size: 8.4pt; background: #0f1b26; color: #e3edf5; padding: 8px 10px;
      border-radius: 6px; white-space: pre-wrap; }
ul, ol { margin: 4px 0 8px 18px; padding: 0; } li { margin: 2px 0; }
.doc { page-break-before: always; } .doc:first-child { page-break-before: auto; }
.foot { color: #6b7a8c; font-size: 8pt; margin-top: 14px; }
"""


def main():
    *mds, pdf = sys.argv[1:]
    body = "".join(f'<section class="doc">{convert(open(m, encoding="utf-8").read())}</section>' for m in mds)
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>Smart Lab final report</title>"
            f"<style>{CSS}</style></head><body>{body}<p class='foot'>Smart Lab - GIU BSc thesis, topic 107. "
            f"Generated from the Markdown reports in docs/reports.</p></body></html>")
    tmp = os.path.splitext(pdf)[0] + ".html"
    open(tmp, "w", encoding="utf-8").write(page)
    js = f"""
import {{ chromium }} from 'playwright-core';
import {{ pathToFileURL }} from 'node:url';
const b = await chromium.launch({{ channel: 'msedge' }}).catch(() => chromium.launch({{ channel: 'chrome' }}));
const p = await b.newPage();
await p.goto(pathToFileURL({tmp!r}).href, {{ waitUntil: 'load' }});
await p.pdf({{ path: {pdf!r}, format: 'A4', printBackground: true,
  margin: {{ top: '14mm', bottom: '14mm', left: '12mm', right: '12mm' }} }});
await b.close();
"""
    runner = os.path.join(ROOT, "frontend", "e2e", "_render_report.mjs")
    open(runner, "w", encoding="utf-8").write(js)
    try:
        subprocess.run(["node", runner], cwd=os.path.join(ROOT, "frontend"), check=True)
    finally:
        os.remove(runner)
        os.remove(tmp)
    print("pdf:", pdf, os.path.getsize(pdf), "bytes")


if __name__ == "__main__":
    main()
