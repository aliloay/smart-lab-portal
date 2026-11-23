"""CSV exports that are safe to open in Excel (ultracode B-08, 2026-11-22).

A cell that starts with = + - @ (or a tab / carriage return) is run as a formula by spreadsheet programs. Free text
reaches the exports (a sign-up's full name, event messages), so such a cell gets a leading apostrophe - Excel and
LibreOffice then show it as text. Numbers are left alone (a negative temperature stays a number)."""
import csv

_DANGER = ("=", "+", "-", "@", "\t", "\r")


_TRIM = " \t\r\n"


def safe_cell(v):
    # Gemini 23 Nov: " =cmd" or a line break before "=cmd" is a formula too once the cell is trimmed.
    if isinstance(v, str) and v.lstrip(_TRIM).startswith(_DANGER):
        return "'" + v
    return v


class _SafeWriter:
    def __init__(self, buf, **kw):
        self._w = csv.writer(buf, **kw)

    def writerow(self, row):
        return self._w.writerow([safe_cell(v) for v in row])

    def writerows(self, rows):
        for r in rows:
            self.writerow(r)


def writer(buf, **kw) -> _SafeWriter:
    return _SafeWriter(buf, **kw)
