"""smartlab - read-only, agent-native CLI for the Smart Research Lab (CLI-Anything methodology).

It inspects; it never acts. No command can unlock a door, drive a relay, move a robot, write OPC UA, run an n8n
workflow, flash firmware, shut down a PC or change the database. Those command groups do not exist, and the network
layer (utils/api_client.py) refuses any request that is not on its read-only allow-list.

Every command supports --json (one envelope: success, command, timestamp, source, freshness, data, warnings, errors).
Run with no command for the interactive REPL.
"""
from __future__ import annotations

import getpass
import json
import os
import shlex
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import click

from . import __version__
from .core import ai as ai_core
from .core import devices as dev
from .core import doctor as doctor_core
from .core import repo as repo_core
from .core import services as svc
from .utils.api_client import Client
from .utils.config import Config
from .utils.errors import EXIT_ERROR, InvalidInput, SmartlabError
from .utils.output import dumps, envelope, human

CTX = dict(help_option_names=["-h", "--help"])


class State:
    def __init__(self, as_json: bool):
        self.json = as_json
        self.cfg = Config.load()
        self.client = Client(self.cfg)


def emit(ctx: click.Context, command: str, data: Any, source: str, warnings: Optional[list] = None,
         freshness: Optional[str] = None) -> None:
    e = envelope(command, data, source, warnings=warnings, freshness=freshness)
    click.echo(dumps(e) if ctx.obj.json else human(e))


def handle_error(command: str, source: str = "smartlab-cli") -> Callable:
    """Consistent errors: JSON envelope (success=false) or a readable line, and a stable exit code."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            ctx = click.get_current_context()
            try:
                return fn(*a, **k)
            except SmartlabError as err:
                e = envelope(command, None, source, success=False, errors=[err.as_dict()])
                click.echo(dumps(e) if ctx.obj.json else human(e), err=not ctx.obj.json)
                ctx.exit(err.exit_code)
            except (OSError, ValueError) as err:
                e = envelope(command, None, source, success=False,
                             errors=[{"code": "ERROR", "message": f"{type(err).__name__}: {err}"}])
                click.echo(dumps(e) if ctx.obj.json else human(e), err=not ctx.obj.json)
                ctx.exit(EXIT_ERROR)
        return wrapper
    return deco


@click.group(context_settings=CTX, invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable JSON envelope.")
@click.version_option(__version__, prog_name="smartlab")
@click.pass_context
def cli(ctx: click.Context, as_json: bool) -> None:
    """Smart Research Lab - read-only inspection CLI for AI agents and people."""
    ctx.obj = State(as_json)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ------------------------------------------------------------------------------------------- top ---
@cli.command()
@click.pass_context
@handle_error("status", "smartlab-api+local-probes")
def status(ctx):
    """One-screen overview: portal, services, ESP32 boards, AI."""
    c: Client = ctx.obj.client
    out: dict[str, Any] = {}
    warns = []
    h, ms = c.portal("/health", auth=False)
    out["portal"] = {"status": "ONLINE" if h else "UNKNOWN", "ms": ms,
                     "build": (h.get("version") or {}).get("id") if isinstance(h, dict) else None}
    out["services"] = {s["service"]: s["status"] for s in svc.services(c)}
    try:
        rows, _ = dev.all_devices(c)
        esp = dev.filtered(rows, dev.ESP32_TYPES)
        out["esp32"] = {r["uid"]: r["status"] for r in esp}
        out["devices"] = dev.summary(rows)
    except SmartlabError as e:
        out["esp32"] = "NOT_ACCESSIBLE"
        warns.append(f"devices: {e.message} {e.hint}".strip())
    try:
        m = ai_core.ollama_models(c)
        out["ai_models_loaded"] = [f"{r['model']} ({r['device']})" for r in m["rows"] if r["loaded"]] or "none loaded"
    except SmartlabError as e:
        out["ai_models_loaded"] = "NOT_ACCESSIBLE"
        warns.append(f"ollama: {e.message}")
    emit(ctx, "status", out, "smartlab-api+local-probes", warns)


@cli.command()
@click.pass_context
@handle_error("doctor", "smartlab-api+local-probes")
def doctor(ctx):
    """Run every health check (PASS / WARN / FAIL / SKIP with evidence)."""
    emit(ctx, "doctor", doctor_core.run(ctx.obj.client), "smartlab-api+local-probes")


@cli.command()
@click.pass_context
@handle_error("health", "smartlab-api")
def health(ctx):
    """Portal health and build stamp (no sign-in needed)."""
    d, ms = ctx.obj.client.portal("/health", auth=False)
    emit(ctx, "health", {**(d if isinstance(d, dict) else {"raw": d}), "ms": ms}, "smartlab-api /api/health")


# ---------------------------------------------------------------------------------------- auth -----
@cli.group()
def auth():
    """Portal sign-in for the commands that need staff/admin (token kept locally, 8 h)."""


@auth.command("login")
@click.option("--username", "-u", default=lambda: os.environ.get("SMARTLAB_USERNAME", ""), help="Username or email.")
@click.pass_context
@handle_error("auth login", "smartlab-api /api/auth/login")
def auth_login(ctx, username):
    """Sign in (password is asked for, or read from SMARTLAB_PASSWORD). Writes a LOGIN audit entry in the portal."""
    if not username:
        username = click.prompt("Username or email")
    pw = os.environ.get("SMARTLAB_PASSWORD") or getpass.getpass("Password: ")
    c: Client = ctx.obj.client
    r = c.login(username, pw)
    c.save_token(r["access_token"], 8 * 3600 - 120, {"role": r.get("role"), "user_id": r.get("user_id")})
    emit(ctx, "auth login", {"signed_in": True, "role": r.get("role"), "expires_in_h": 8,
                             "stored_at": "~/.smartlab/token.json"}, "smartlab-api /api/auth/login")


@auth.command("status")
@click.pass_context
@handle_error("auth status", "smartlab-api /api/auth/me")
def auth_status(ctx):
    """Who the CLI is signed in as."""
    c: Client = ctx.obj.client
    if not c.token():
        emit(ctx, "auth status", {"signed_in": False, "hint": "smartlab auth login"}, "local token file")
        return
    me, _ = c.portal("/auth/me")
    emit(ctx, "auth status", {"signed_in": True, "role": me.get("role"), "user_id": me.get("id")},
         "smartlab-api /api/auth/me")


@auth.command("logout")
@click.pass_context
@handle_error("auth logout", "local token file")
def auth_logout(ctx):
    """Forget the local token (nothing is changed in the portal)."""
    emit(ctx, "auth logout", {"token_removed": Client.forget_token()}, "local token file")


# ------------------------------------------------------------------------------------- system ------
@cli.group()
def system():
    """Laptop, services, containers and versions."""


@system.command("services")
@click.pass_context
@handle_error("system services", "local health probes")
def system_services(ctx):
    """Probe every local service (portal, n8n, face, cameras, knowledge, voice, Ollama)."""
    rows = svc.services(ctx.obj.client)
    emit(ctx, "system services", {"rows": rows, "columns": ["service", "status", "ms", "what"]}, "local health probes")


@system.command("containers")
@click.pass_context
@handle_error("system containers", "docker ps")
def system_containers(ctx):
    """Docker containers and their health (docker ps, read-only)."""
    r = svc.docker_containers()
    emit(ctx, "system containers", {"status": r["status"], "rows": r["containers"],
                                    "columns": ["name", "health", "status"]}, "docker ps")


@system.command("resources")
@click.pass_context
@handle_error("system resources", "local OS")
def system_resources(ctx):
    """RAM, disks and GPU memory."""
    emit(ctx, "system resources", svc.resources(ctx.obj.client), "local OS (+ nvidia-smi)")


@system.command("health")
@click.pass_context
@handle_error("system health", "smartlab-api /api/system/health")
def system_health(ctx):
    """The portal's own aggregate health view (staff)."""
    d, ms = ctx.obj.client.portal("/system/health")
    emit(ctx, "system health", d, "smartlab-api /api/system/health")


@system.command("version")
@click.pass_context
@handle_error("system version", "smartlab-api+git")
def system_version(ctx):
    """CLI version, portal build stamp and repo HEAD."""
    c: Client = ctx.obj.client
    out: dict[str, Any] = {"cli": __version__}
    try:
        h, _ = c.portal("/health", auth=False)
        out["portal_build"] = h.get("version")
    except SmartlabError as e:
        out["portal_build"] = f"NOT_ACCESSIBLE ({e.message})"
    try:
        out["repo"] = repo_core.git_status(c.cfg.repo)["head"]
    except SmartlabError as e:
        out["repo"] = f"NOT_CONFIGURED ({e.message})"
    emit(ctx, "system version", out, "smartlab-api+git")


# ------------------------------------------------------------------------------------ devices ------
def _rows_emit(ctx, command, rows, source, columns, extra=None):
    emit(ctx, command, {"count": len(rows), **(extra or {}), "rows": rows, "columns": columns}, source)


DEV_COLS = ["uid", "type", "status", "age", "ip", "firmware", "lab"]


@cli.group()
def devices():
    """Every registered device (portal API, staff sign-in)."""


@devices.command("list")
@click.option("--type", "dtype", help="Filter by device type, e.g. SENSOR_NODE, PC, ROBOT.")
@click.option("--status", type=click.Choice(["ONLINE", "OFFLINE", "STALE", "UNKNOWN", "DEGRADED"], case_sensitive=False))
@click.option("--include-retired", is_flag=True)
@click.pass_context
@handle_error("devices list", "smartlab-api /api/devices")
def devices_list(ctx, dtype, status, include_retired):
    """All devices with a status label (ONLINE/OFFLINE/STALE/DEGRADED/UNKNOWN), age, IP, firmware."""
    rows, _ = dev.all_devices(ctx.obj.client, include_retired)
    rows = dev.filtered(rows, {dtype.upper()} if dtype else None, status)
    _rows_emit(ctx, "devices list", rows, "smartlab-api /api/devices", DEV_COLS)


@devices.command("inspect")
@click.argument("uid")
@click.pass_context
@handle_error("devices inspect", "smartlab-api /api/devices")
def devices_inspect(ctx, uid):
    """One device in detail (components, note, freshness)."""
    emit(ctx, "devices inspect", dev.inspect(ctx.obj.client, uid), "smartlab-api /api/devices")


@devices.command("offline")
@click.pass_context
@handle_error("devices offline", "smartlab-api /api/devices")
def devices_offline(ctx):
    """Everything that is not ONLINE right now."""
    rows, _ = dev.all_devices(ctx.obj.client)
    _rows_emit(ctx, "devices offline", [r for r in rows if r["status"] != "ONLINE"],
               "smartlab-api /api/devices", DEV_COLS + ["note"])


@devices.command("summary")
@click.pass_context
@handle_error("devices summary", "smartlab-api /api/devices")
def devices_summary(ctx):
    """Counts per device type and status."""
    rows, _ = dev.all_devices(ctx.obj.client)
    emit(ctx, "devices summary", dev.summary(rows), "smartlab-api /api/devices")


# -------------------------------------------------------------------------------------- esp32 ------
@cli.group()
def esp32():
    """The ESP32 boards: master door, environment, bins, ESP32-CAM."""


@esp32.command("list")
@click.pass_context
@handle_error("esp32 list", "smartlab-api /api/devices")
def esp32_list(ctx):
    """The ESP32 boards with status, age, IP and reported firmware."""
    rows, _ = dev.all_devices(ctx.obj.client)
    _rows_emit(ctx, "esp32 list", dev.filtered(rows, dev.ESP32_TYPES), "smartlab-api /api/devices", DEV_COLS)


@esp32.command("inspect")
@click.argument("uid")
@click.pass_context
@handle_error("esp32 inspect", "smartlab-api /api/devices")
def esp32_inspect(ctx, uid):
    """One ESP32 board in detail (components, note, freshness)."""
    d = dev.inspect(ctx.obj.client, uid)
    if d["type"] not in dev.ESP32_TYPES:
        raise InvalidInput(f"{uid} is a {d['type']}, not an ESP32 board", "smartlab esp32 list")
    emit(ctx, "esp32 inspect", d, "smartlab-api /api/devices")


@esp32.command("firmware")
@click.pass_context
@handle_error("esp32 firmware", "smartlab-api /api/devices + repo firmware/")
def esp32_firmware(ctx):
    """Reported firmware vs the version declared in the repo's firmware sources."""
    c: Client = ctx.obj.client
    rows, _ = dev.all_devices(c)
    cmp_ = repo_core.firmware_compare(c.cfg.repo, dev.filtered(rows, dev.ESP32_TYPES))
    _rows_emit(ctx, "esp32 firmware", cmp_, "smartlab-api /api/devices + repo firmware/",
               ["uid", "type", "reported", "source_folder", "matches_source"])


@esp32.command("ping")
@click.pass_context
@handle_error("esp32 ping", "ICMP from this laptop")
def esp32_ping(ctx):
    """One ping to each ESP32 address the portal knows (Wi-Fi reachability from this laptop)."""
    rows, _ = dev.all_devices(ctx.obj.client)
    out = []
    for r in dev.filtered(rows, dev.ESP32_TYPES):
        p = svc.ping(r["ip"]) if r["ip"] else {"reachable": None, "ms": None}
        out.append({"uid": r["uid"], "ip": r["ip"], "reachable": p.get("reachable"), "ms": p.get("ms")})
    _rows_emit(ctx, "esp32 ping", out, "ICMP from this laptop", ["uid", "ip", "reachable", "ms"])


# ------------------------------------------------------------------------------------ cameras ------
@cli.group()
def cameras():
    """Security camera services: is a picture arriving, analysis speed, engines."""


@cameras.command("status")
@click.pass_context
@handle_error("cameras status", "camera services /metrics")
def cameras_status(ctx):
    """Per camera: service up? picture arriving? capture/analysis fps, detector engine."""
    rows = svc.camera_metrics(ctx.obj.client)
    _rows_emit(ctx, "cameras status", rows, "camera services /metrics (127.0.0.1:5100/5101)",
               ["camera", "service", "picture", "capture_fps", "analysis_fps", "detect_ms", "open_failures", "detector"])


@cameras.command("list")
@click.pass_context
@handle_error("cameras list", "smartlab-api /api/devices")
def cameras_list(ctx):
    """Camera devices as the portal sees them."""
    rows, _ = dev.all_devices(ctx.obj.client)
    _rows_emit(ctx, "cameras list", dev.filtered(rows, dev.CAMERA_TYPES), "smartlab-api /api/devices", DEV_COLS + ["note"])


# ------------------------------------------------------------------------------------- robots ------
@cli.group()
def robots():
    """UR5e / FANUC digital twins - read-only telemetry. No motion command exists here."""


@robots.command("list")
@click.pass_context
@handle_error("robots list", "smartlab-api /api/devices")
def robots_list(ctx):
    """Robot devices as the portal sees them (status, age, note)."""
    rows, _ = dev.all_devices(ctx.obj.client)
    _rows_emit(ctx, "robots list", dev.filtered(rows, dev.ROBOT_TYPES), "smartlab-api /api/devices", DEV_COLS + ["note"])


@robots.command("status")
@click.pass_context
@handle_error("robots status", "smartlab-api /api/robots")
def robots_status(ctx):
    """Twin state from the portal (mode, connection, simulated or real)."""
    rows, _ = dev.robots(ctx.obj.client)
    emit(ctx, "robots status", {"count": len(rows), "rows": rows}, "smartlab-api /api/robots")


# ---------------------------------------------------------------------------------------- pcs ------
@cli.group()
def pcs():
    """Lab PCs (agents report to the portal)."""


@pcs.command("list")
@click.option("--status", type=click.Choice(["ONLINE", "OFFLINE", "STALE", "UNKNOWN", "DEGRADED"], case_sensitive=False))
@click.pass_context
@handle_error("pcs list", "smartlab-api /api/devices")
def pcs_list(ctx, status):
    """Lab PCs with status label and last report."""
    rows, _ = dev.all_devices(ctx.obj.client)
    _rows_emit(ctx, "pcs list", dev.filtered(rows, dev.PC_TYPES, status), "smartlab-api /api/devices", DEV_COLS)


@pcs.command("inspect")
@click.argument("uid")
@click.pass_context
@handle_error("pcs inspect", "smartlab-api /api/devices")
def pcs_inspect(ctx, uid):
    """One lab PC in detail."""
    emit(ctx, "pcs inspect", dev.inspect(ctx.obj.client, uid), "smartlab-api /api/devices")


# ----------------------------------------------------------------------------------------- ai ------
@cli.group()
def ai():
    """Local AI: Ollama models, which model each assistant uses, the camera-first GPU gate."""


@ai.command("models")
@click.pass_context
@handle_error("ai models", "ollama /api/tags + /api/ps")
def ai_models(ctx):
    """Installed Ollama models, size, which are loaded and on CPU or GPU."""
    emit(ctx, "ai models", ai_core.ollama_models(ctx.obj.client), "ollama /api/tags + /api/ps")


@ai.command("status")
@click.pass_context
@handle_error("ai status", "knowledge-service + smartlab-api + ollama")
def ai_status(ctx):
    """Knowledge assistant model, portal assistant model/health, GPU gate decision."""
    emit(ctx, "ai status", ai_core.assistants(ctx.obj.client), "knowledge-service + smartlab-api")


@ai.command("config")
@click.pass_context
@handle_error("ai config", "tools/knowledge/config.json")
def ai_config(ctx):
    """Knowledge assistant settings (keys and passwords removed)."""
    emit(ctx, "ai config", ai_core.knowledge_config(ctx.obj.client), "tools/knowledge/config.json (redacted)")


# ---------------------------------------------------------------------------------- knowledge ------
@cli.group()
def knowledge():
    """The project knowledge vault and search (no AI generation)."""


@knowledge.command("status")
@click.pass_context
@handle_error("knowledge status", "knowledge-service /status")
def knowledge_status(ctx):
    """Knowledge service: index build time, embeddings, assistant model."""
    d, ms = ctx.obj.client.kb("/status")
    emit(ctx, "knowledge status", {**d, "ms": ms}, "knowledge-service /status")


@knowledge.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", default=5, type=click.IntRange(1, 10))
@click.pass_context
@handle_error("knowledge search", "knowledge-service /ask route=lookup")
def knowledge_search(ctx, query, limit):
    """Find the documents/code that answer QUERY (cited sources, no model run)."""
    q = " ".join(query).strip()
    if len(q) < 2:
        raise InvalidInput("query too short")
    emit(ctx, "knowledge search", ai_core.knowledge_search(ctx.obj.client, q, limit),
         "knowledge-service /ask route=lookup")


# --------------------------------------------------------------------------------- automation ------
@cli.group()
def automation():
    """n8n workflow DEFINITIONS from the repo copies. Nothing is run, activated or edited."""


@automation.command("list")
@click.pass_context
@handle_error("automation list", "repo automation/n8n/json")
def automation_list(ctx):
    """Every n8n workflow definition: triggers (webhook / schedule), nodes, HTTP calls."""
    rows = repo_core.workflows(ctx.obj.client.cfg.repo)
    _rows_emit(ctx, "automation list", rows, "repo automation/n8n/json", ["name", "triggers", "nodes", "http_calls"])


@automation.command("inspect")
@click.argument("name_or_id")
@click.pass_context
@handle_error("automation inspect", "repo automation/n8n/json")
def automation_inspect(ctx, name_or_id):
    """One workflow definition: node list and portal endpoints it calls (redacted)."""
    emit(ctx, "automation inspect", repo_core.workflow(ctx.obj.client.cfg.repo, name_or_id), "repo automation/n8n/json",
         freshness="repo copy (may differ from the live n8n)")


# ----------------------------------------------------------------------------------- network -------
@cli.group()
def network():
    """Laptop network adapters and reachability."""


@network.command("interfaces")
@click.pass_context
@handle_error("network interfaces", "ipconfig")
def network_interfaces(ctx):
    """IPv4 address and gateway per network adapter."""
    rows = svc.interfaces()
    _rows_emit(ctx, "network interfaces", rows, "ipconfig", ["adapter", "ipv4", "gateway"])


@network.command("ping")
@click.argument("host")
@click.pass_context
@handle_error("network ping", "ICMP")
def network_ping(ctx, host):
    """One ping to HOST (IP or hostname)."""
    emit(ctx, "network ping", svc.ping(host), "ICMP from this laptop")


# ---------------------------------------------------------------------------------- firmware -------
@cli.group()
def firmware():
    """Firmware versions declared in the repo sources (read-only; nothing is flashed)."""


@firmware.command("inventory")
@click.pass_context
@handle_error("firmware inventory", "repo firmware/")
def firmware_inventory(ctx):
    """Firmware version declared in each firmware/ folder."""
    rows = repo_core.firmware(ctx.obj.client.cfg.repo)
    _rows_emit(ctx, "firmware inventory", rows, "repo firmware/", ["folder", "version", "declared_in"])


# -------------------------------------------------------------------------------------- logs -------
@cli.group()
def logs():
    """Service logs (redacted)."""


@logs.command("list")
@click.pass_context
@handle_error("logs list", "local log files")
def logs_list(ctx):
    """Known log files (logs/, master serial log) with size and modified time."""
    c = ctx.obj.client.cfg
    _rows_emit(ctx, "logs list", repo_core.logs_list(c.repo, c.serial_log), "local log files",
               ["log", "size_kb", "modified", "path"])


@logs.command("recent")
@click.argument("log_name")
@click.option("--lines", "-n", default=40, type=int)
@click.option("--errors", "errors_only", is_flag=True, help="Only error/warning/offline lines.")
@click.pass_context
@handle_error("logs recent", "local log files")
def logs_recent(ctx, log_name, lines, errors_only):
    """Last lines of LOG_NAME (a name from `smartlab logs list`)."""
    c = ctx.obj.client.cfg
    match = [l for l in repo_core.logs_list(c.repo, c.serial_log) if l["log"] == log_name]
    if not match:
        raise InvalidInput(f"unknown log {log_name!r}", "smartlab logs list")
    out = repo_core.logs_tail(Path(match[0]["path"]), lines, errors_only)
    emit(ctx, "logs recent", {"log": log_name, "lines": out}, f"log file {log_name}", freshness="file contents")


# ----------------------------------------------------------------------------------- reports -------
@cli.group()
def reports():
    """Project reports and benchmarks in the repo."""


@reports.command("list")
@click.option("--limit", default=20, type=click.IntRange(1, 200))
@click.pass_context
@handle_error("reports list", "repo docs/reports, reports/, docs/benchmarks")
def reports_list(ctx, limit):
    """Most recent reports and benchmarks (.md) in the repo."""
    _rows_emit(ctx, "reports list", repo_core.reports(ctx.obj.client.cfg.repo, limit), "repo",
               ["report", "modified", "path"])


@reports.command("latest")
@click.pass_context
@handle_error("reports latest", "repo")
def reports_latest(ctx):
    """Read the most recently changed report (redacted, first 6000 characters)."""
    r = repo_core.reports(ctx.obj.client.cfg.repo, 1)
    if not r:
        raise InvalidInput("no reports found")
    emit(ctx, "reports latest", repo_core.report_read(ctx.obj.client.cfg.repo, r[0]["path"]), "repo",
         freshness="file contents")


@reports.command("read")
@click.argument("path")
@click.pass_context
@handle_error("reports read", "repo")
def reports_read(ctx, path):
    """Read a .md report inside the repo (first 6000 characters, redacted)."""
    emit(ctx, "reports read", repo_core.report_read(ctx.obj.client.cfg.repo, path), "repo", freshness="file contents")


# ------------------------------------------------------------------------------------ github -------
@cli.group()
def github():
    """Local git state vs GitHub (no fetch, no push)."""


@github.command("status")
@click.pass_context
@handle_error("github status", "git")
def github_status(ctx):
    """Branch, HEAD, modified/untracked files, commits ahead/behind origin/main (last fetch)."""
    emit(ctx, "github status", repo_core.git_status(ctx.obj.client.cfg.repo), "git (local refs)")


@github.command("branches")
@click.pass_context
@handle_error("github branches", "git")
def github_branches(ctx):
    """Local branches by last commit, and the git worktrees."""
    rows = repo_core.git_branches(ctx.obj.client.cfg.repo)
    _rows_emit(ctx, "github branches", rows, "git (local refs)", ["branch", "date", "last_commit"])


@github.command("compare")
@click.option("--base", default="origin/main")
@click.pass_context
@handle_error("github compare", "git")
def github_compare(ctx, base):
    """Commits and files on HEAD that are not on BASE (default origin/main)."""
    emit(ctx, "github compare", repo_core.git_compare(ctx.obj.client.cfg.repo, base), "git (local refs)")


# -------------------------------------------------------------------------------------- repl -------
@cli.command()
@click.pass_context
def repl(ctx):
    """Interactive mode (default when no command is given)."""
    from .utils.repl_skin import ReplSkin
    skin = ReplSkin("smartlab", version=__version__)
    skin.print_banner()
    skin.info("Read-only. Try: status | doctor | devices list | esp32 list | ai status | knowledge search <q> | help | exit")
    # prompt_toolkit needs a real console; piped input (agents, scripts) falls back to plain input().
    try:
        session = skin.create_prompt_session() if sys.stdin.isatty() and sys.stdout.isatty() else None
    except Exception:  # noqa: BLE001 - e.g. NoConsoleScreenBufferError on Windows
        session = None
    while True:
        try:
            line = skin.get_input(session).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        if line == "help":
            skin.help({name: (cmd.help or "").split("\n")[0] for name, cmd in cli.commands.items() if name != "repl"})
            continue
        args = (["--json"] if ctx.obj.json else []) + shlex.split(line)
        try:
            cli.main(args=args, prog_name="smartlab", standalone_mode=False)
        except click.exceptions.Exit:
            pass
        except click.ClickException as e:
            skin.error(e.format_message())
        except SystemExit:
            pass
    skin.print_goodbye()


def main() -> None:
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    cli(prog_name="smartlab")


if __name__ == "__main__":
    main()
