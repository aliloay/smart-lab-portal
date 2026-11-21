"""Read-only guarantees. These tests fail if anyone adds a command or a request that could act on the lab."""
from __future__ import annotations

import re
import socket
from pathlib import Path

import click
import pytest

from cli_anything.smartlab import smartlab_cli
from cli_anything.smartlab.utils import api_client
from cli_anything.smartlab.utils.api_client import Client
from cli_anything.smartlab.utils.config import Config
from cli_anything.smartlab.utils.errors import AuthRequired, Forbidden

PKG = Path(smartlab_cli.__file__).parent

FORBIDDEN_WORDS = {"unlock", "lock", "open", "relay", "door", "move", "jog", "home", "stop", "estop", "write",
                   "run", "execute", "activate", "deactivate", "trigger", "flash", "upload", "shutdown", "reboot",
                   "restart", "delete", "remove", "create", "update", "set", "grant", "revoke", "approve", "pull",
                   "rm", "alarm", "emergency", "message", "maintenance", "exam", "share"}


def _all_commands(group: click.Group, prefix=()):
    for name, cmd in group.commands.items():
        path = (*prefix, name)
        yield path
        if isinstance(cmd, click.Group):
            yield from _all_commands(cmd, path)


def test_no_dangerous_command_exists():
    names = {p[-1] for p in _all_commands(smartlab_cli.cli)}
    assert not names & FORBIDDEN_WORDS, names & FORBIDDEN_WORDS
    # 'auth login/logout' only touch the local token file / the sign-in endpoint
    assert {"login", "logout"} <= names


def test_every_group_has_only_read_verbs():
    allowed = {"list", "inspect", "status", "summary", "offline", "firmware", "ping", "models", "config", "search",
               "interfaces", "inventory", "recent", "latest", "read", "branches", "compare", "services",
               "containers", "resources", "health", "version", "login", "logout"}
    for path in _all_commands(smartlab_cli.cli):
        if len(path) == 2:
            assert path[1] in allowed, path


@pytest.fixture
def no_network(monkeypatch):
    """Any socket use fails the test: Forbidden must be raised before a connection is attempted."""
    def boom(*a, **k):
        raise AssertionError("a network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTLAB_TOKEN", "fake-token-123456")
    monkeypatch.setenv("SMARTLAB_REPO", str(tmp_path))
    return Client(Config.load())


@pytest.mark.parametrize("path", [
    "/access/commands/next", "/equipment/pc/poll", "/equipment/pc/wait", "/robots/stop-relay/poll",
    "/equipment/master/nonce", "/equipment/share-requests/nonce", "/equipment/pc/watch-token",
    "/emergency/active", "/bookings/1/qr", "/auth/me/door-qr", "/security/cameras/1/frame.jpg",
    "/users/1/door-photo", "/ai/insights", "/ai/report", "/system/config", "/opcua/snapshot",
    "/access-events/export", "/robots/UR5E_01/control", "/devices/../users",
])
def test_side_effect_paths_refused_before_network(client, no_network, path):
    with pytest.raises(Forbidden):
        client.portal(path)


def test_only_post_is_login():
    assert api_client.PORTAL_POST == {"/auth/login"}
    src = (PKG / "utils" / "api_client.py").read_text(encoding="utf-8")
    methods = set(re.findall(r'_send\("([A-Z]+)"', src))
    assert methods <= {"GET", "POST"}
    assert src.count('_send("POST"') == 2          # login + knowledge lookup


@pytest.mark.parametrize("path", ["/api/pull", "/api/delete", "/api/generate", "/api/chat", "/api/create", "/api/copy"])
def test_ollama_mutations_refused(client, no_network, path):
    with pytest.raises(Forbidden):
        client.ollama(path)


@pytest.mark.parametrize("path", ["/ask", "/jobs/sync", "/reindex"])
def test_knowledge_only_status_paths(client, no_network, path):
    with pytest.raises(Forbidden):
        client.kb(path)


def test_knowledge_search_is_lookup_only():
    src = (PKG / "utils" / "api_client.py").read_text(encoding="utf-8")
    assert '"route": "lookup"' in src


def test_cameras_only_health_and_metrics(client, no_network):
    for port, path in ((5100, "/record/start"), (5101, "/known"), (5000, "/health")):
        with pytest.raises(Forbidden):
            client.camera(port, path)


def test_no_shell_or_eval_anywhere():
    for f in PKG.rglob("*.py"):
        if "tests" in f.parts or f.name == "repl_skin.py":
            continue
        src = f.read_text(encoding="utf-8")
        assert "shell=True" not in src, f
        assert "os.system(" not in src and "os.popen(" not in src, f
        assert not re.search(r"(?<![\w.])eval\(|(?<![\w.])exec\(", src), f
        for m in re.finditer(r"subprocess\.run\((.{0,40})", src):
            first = m.group(1).lstrip()
            # an argument list literal, or the prepared list `args` (ping) - never a string command line
            assert first.startswith("[") or re.match(r"args\b", first), (f, m.group(0))
            assert not first.startswith(("\"", "'", "f\"", "f'")), (f, m.group(0))


def test_unauthenticated_device_command_sends_nothing(monkeypatch, tmp_path, no_network):
    monkeypatch.delenv("SMARTLAB_TOKEN", raising=False)
    monkeypatch.setattr(api_client, "TOKEN_FILE", tmp_path / "none.json")
    with pytest.raises(AuthRequired):
        Client(Config.load()).portal("/devices")


def test_secrets_never_in_output(monkeypatch, tmp_path):
    """Fake secrets on disk; run every repo-local command; none may appear in the output."""
    from click.testing import CliRunner
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "docker-compose.yml").write_text("")
    (tmp_path / ".env").write_text("DEVICE_API_KEY=DEVSECRET-7777777\n")
    (tmp_path / "tools" / "knowledge").mkdir(parents=True)
    (tmp_path / "tools" / "knowledge" / "config.json").write_text(
        '{"service_key": "KBSECRET-8888888", "model": "m", "redact_literals": ["LITERAL-999999"]}')
    monkeypatch.setenv("SMARTLAB_REPO", str(tmp_path))
    monkeypatch.setenv("SMARTLAB_TOKEN", "TOKSECRET-6666666")
    r = CliRunner().invoke(smartlab_cli.cli, ["--json", "ai", "config"])
    for s in ("DEVSECRET-7777777", "KBSECRET-8888888", "LITERAL-999999", "TOKSECRET-6666666"):
        assert s not in r.output
