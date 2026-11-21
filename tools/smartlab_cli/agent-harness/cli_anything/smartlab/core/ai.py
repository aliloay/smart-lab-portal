"""Local AI: Ollama models, the knowledge service (vault search, model, GPU gate) and the portal assistant status."""
from __future__ import annotations

from typing import Any

from ..utils.api_client import Client
from ..utils.errors import SmartlabError


def ollama_models(c: Client) -> dict:
    tags, _ = c.ollama("/api/tags")
    ps, _ = c.ollama("/api/ps")
    ver, _ = c.ollama("/api/version")
    loaded = {m.get("name"): m for m in (ps or {}).get("models", [])}
    rows = []
    for m in (tags or {}).get("models", []):
        name = m.get("name")
        lm = loaded.get(name)
        rows.append({"model": name, "size_gb": round((m.get("size") or 0) / 1e9, 2),
                     "params": (m.get("details") or {}).get("parameter_size"),
                     "quant": (m.get("details") or {}).get("quantization_level"),
                     "loaded": bool(lm),
                     "device": None if not lm else ("gpu" if (lm.get("size_vram") or 0) > 0 else "cpu"),
                     "expires_at": lm.get("expires_at") if lm else None})
    return {"ollama_version": (ver or {}).get("version"), "rows": rows,
            "columns": ["model", "size_gb", "params", "quant", "loaded", "device"]}


def assistants(c: Client) -> dict:
    """Which model each assistant uses: knowledge service (config/status) and portal assistant (/api/ai/status)."""
    out: dict[str, Any] = {}
    kcfg = c.cfg.knowledge_config()
    try:
        st, _ = c.kb("/status")
        out["knowledge_assistant"] = {"model": st.get("model"), "index_built": st.get("index_built"),
                                      "embeddings": st.get("embeddings"), "source": "knowledge-service /status"}
    except SmartlabError as e:
        out["knowledge_assistant"] = {"model": kcfg.get("agent_model") or kcfg.get("model"),
                                      "source": "tools/knowledge/config.json (service not reachable)",
                                      "detail": e.message}
    try:
        st, _ = c.portal("/ai/status")
        out["portal_assistant"] = {**({k: v for k, v in st.items()} if isinstance(st, dict) else {"raw": st}),
                                   "source": "portal /api/ai/status"}
    except SmartlabError as e:
        out["portal_assistant"] = {"status": "NOT_ACCESSIBLE", "detail": e.message, **({"hint": e.hint} if e.hint else {})}
    try:
        g, _ = c.kb("/gpu-gate")
        out["gpu_gate"] = {"device": g.get("device"), "reason": g.get("reason"),
                           "cameras": [{"port": x.get("port"), "state": x.get("state"), "fps": x.get("fps")}
                                       for x in g.get("cameras", [])]}
    except SmartlabError as e:
        out["gpu_gate"] = {"status": "NOT_ACCESSIBLE", "detail": e.message}
    return out


def knowledge_config(c: Client) -> dict:
    k = c.cfg.knowledge_config()
    if not k:
        raise SmartlabError("tools/knowledge/config.json not found", "Set SMARTLAB_REPO to the Smart Lab repo.")
    return k


def knowledge_search(c: Client, query: str, limit: int = 5) -> dict:
    events, ms = c.kb_search(query)
    meta = next((e for e in events if e.get("type") == "meta"), {})
    done = next((e for e in events if e.get("type") == "done"), {})
    cites = meta.get("citations") or done.get("citations") or []
    rows = [{"n": x.get("n"), "source": x.get("source"), "heading": x.get("heading"),
             "label": x.get("label"), "score": round(x["score"], 3) if isinstance(x.get("score"), (int, float)) else x.get("score")}
            for x in cites[:limit]]
    return {"query": query, "route": done.get("route") or meta.get("route") or "lookup", "search_ms": ms,
            "rows": rows, "columns": ["n", "source", "heading", "label", "score"],
            "note": "document search only (route=lookup): the AI model was not run"}
