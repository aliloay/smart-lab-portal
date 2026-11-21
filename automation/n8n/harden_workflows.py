"""Harden n8n workflows (audit F-11): error workflow, HTTP timeouts, retries on webhook flows.
Usage: py n8n_harden.py <input_dir> <output_dir>   (input = live export or repo copies; files never edited in place)"""
import copy, json, os, sys

ERR_ID, ERR_NAME = "SmartLab00ErrHnd", "Smart Lab 00 - Error handler"
CRED = {"httpHeaderAuth": {"id": "1V0PfllJdkPmPubj", "name": "Smart Lab automation key"}}
TIMEOUT_MS = 15000
WEBHOOK_RETRY = {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}


def post(name, url, body, pos, nid):
    return {"id": nid, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.5, "position": pos,
            "parameters": {"method": "POST", "url": url, "authentication": "genericCredentialType",
                           "genericAuthType": "httpHeaderAuth", "sendBody": True, "contentType": "json",
                           "specifyBody": "json", "jsonBody": body, "options": {"timeout": TIMEOUT_MS}},
            "credentials": copy.deepcopy(CRED), **WEBHOOK_RETRY, "onError": "continueRegularOutput"}


ERROR_WF = {
    "id": ERR_ID, "name": ERR_NAME, "active": False,
    "nodes": [
        {"id": "e0000000-0000-4000-8000-000000000001", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger",
         "typeVersion": 1, "position": [200, 300], "parameters": {}},
        post("Record Failed Run", "http://backend:8000/api/automation/runs",
             '={{ JSON.stringify({ workflow: String($json.workflow.name || "unknown").slice(0, 48), status: "error", '
             'summary: String(($json.execution.lastNodeExecuted ? "Node " + $json.execution.lastNodeExecuted + ": " : "") + '
             '(($json.execution.error || {}).message || "failed")).slice(0, 500), execution_id: String($json.execution.id || "") }) }}',
             [460, 220], "e0000000-0000-4000-8000-000000000002"),
        post("Raise Alert", "http://backend:8000/api/automation/alerts",
             '={{ JSON.stringify({ severity: "WARNING", title: ("n8n workflow failed: " + String($json.workflow.name || "unknown")).slice(0, 128), '
             'detail: String("Execution " + ($json.execution.id || "?") + ", node " + ($json.execution.lastNodeExecuted || "?") + ": " + '
             '(($json.execution.error || {}).message || "no message")).slice(0, 1900), '
             'dedupe_key: ("n8n-error-" + String($json.workflow.id || "x") + "-" + String($json.execution.id || Date.now())).slice(0, 160) }) }}',
             [460, 400], "e0000000-0000-4000-8000-000000000003"),
    ],
    "connections": {"Error Trigger": {"main": [[{"node": "Record Failed Run", "type": "main", "index": 0},
                                                {"node": "Raise Alert", "type": "main", "index": 0}]]}},
    "settings": {"executionOrder": "v1"}, "tags": [],
}


def harden(d):
    stats = {"timeouts": 0, "retries": 0}
    if d.get("id") == ERR_ID:
        return d, stats
    d.setdefault("settings", {})
    d["settings"]["errorWorkflow"] = ERR_ID
    webhook = any(n["type"].split(".")[-1] == "webhook" for n in d["nodes"])
    for n in d["nodes"]:
        if not n["type"].endswith("httpRequest"):
            continue
        opts = n["parameters"].setdefault("options", {})
        if not opts.get("timeout"):
            opts["timeout"] = TIMEOUT_MS
            stats["timeouts"] += 1
        if webhook and not n.get("retryOnFail"):
            n.update(WEBHOOK_RETRY)
            stats["retries"] += 1
    return d, stats


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    tot = {"files": 0, "timeouts": 0, "retries": 0}
    for f in sorted(os.listdir(src)):
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(src, f), encoding="utf-8"))
        if not isinstance(d, dict) or "nodes" not in d:
            continue
        d, s = harden(d)
        json.dump(d, open(os.path.join(dst, f), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        tot["files"] += 1
        tot["timeouts"] += s["timeouts"]
        tot["retries"] += s["retries"]
    json.dump(ERROR_WF, open(os.path.join(dst, "00-error-handler.json"), "w", encoding="utf-8"), indent=2)
    print(json.dumps(tot))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
