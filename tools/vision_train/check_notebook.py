"""Syntax-check every code cell of a notebook (shell '!' lines skipped).  py check_notebook.py <file.ipynb>"""
import ast
import json
import sys

nb = json.load(open(sys.argv[1], encoding="utf-8"))
n = 0
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "code":
        continue
    src = c["source"] if isinstance(c["source"], str) else "".join(c["source"])
    ast.parse("\n".join(l for l in src.splitlines() if not l.lstrip().startswith("!")), filename=f"cell {i}")
    n += 1
print(f"{n} code cells parse OK")
