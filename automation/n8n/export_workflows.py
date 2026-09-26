"""
Download the Smart Lab workflows from an n8n instance as importable JSON.

    N8N_URL=https://<you>.app.n8n.cloud N8N_API_KEY=... python3 export_workflows.py

Writes json/<id>.json for every workflow whose name starts with "Smart Lab".
Import them into a self-hosted n8n (e.g. the compose `automation` profile):

    docker compose --profile automation exec n8n \\
        n8n import:workflow --separate --input=/workflows

The API key is read from the environment only and never written anywhere.
Standard library only.
"""
import json
import os
import pathlib
import urllib.request

base = os.environ["N8N_URL"].rstrip("/")
key = os.environ["N8N_API_KEY"]
out = pathlib.Path(__file__).with_name("json")
out.mkdir(exist_ok=True)


def get(path):
    req = urllib.request.Request(base + path, headers={"X-N8N-API-KEY": key,
                                                       "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


cursor, n = None, 0
while True:
    page = get("/api/v1/workflows?limit=100" + (f"&cursor={cursor}" if cursor else ""))
    for wf in page["data"]:
        if not wf["name"].startswith("Smart Lab"):
            continue
        keep = {k: wf[k] for k in ("name", "nodes", "connections", "settings") if k in wf}
        (out / f"{wf['id']}.json").write_text(json.dumps(keep, indent=2))
        n += 1
        print("exported", wf["name"])
    cursor = page.get("nextCursor")
    if not cursor:
        break
print(f"{n} workflow(s) written to {out}")
