"""Signed self-update, roll-back, the supervisor and enrollment (2026-11-04): no real portal, no real agent."""
import base64
import hashlib
import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_boot                                           # noqa: E402
import agent_update as U                                    # noqa: E402
import make_bundle                                          # noqa: E402
import pc_agent as A                                        # noqa: E402


@pytest.fixture(scope="module")
def key():
    return make_bundle.new_key()


def bundle(key, seq, files: dict, sign_with=None) -> dict:
    items = [{"name": n, "sha256": hashlib.sha256(b).hexdigest()} for n, b in files.items()]
    manifest = {"seq": seq, "id": f"b{seq}", "files": items}
    return {"manifest": manifest, "sig": make_bundle.sign(U.canonical(manifest), sign_with or key),
            "files": {n: base64.b64encode(b).decode() for n, b in files.items()}}


def test_signature_check(key):
    n = int(key["n"], 16)
    sig = make_bundle.sign(b"hello", key)
    assert U.verify(b"hello", sig, n)
    assert not U.verify(b"hellp", sig, n)
    assert not U.verify(b"hello", format(int(sig, 16) ^ 1, "x"), n)
    assert not U.verify(b"hello", "zz", n) and not U.verify(b"hello", None, n) and not U.verify(b"hello", "0", n)


def test_a_good_bundle_goes_in_and_keeps_the_old_files(key, tmp_path):
    d, n = str(tmp_path), int(key["n"], 16)
    (tmp_path / "pc_agent.py").write_bytes(b"old")
    U.write_state(d, {"seq": 5, "id": "b5"})
    assert U.apply_bundle(d, bundle(key, 6, {"pc_agent.py": b"new", "extra.py": b"x"}), n) == 6
    assert (tmp_path / "pc_agent.py").read_bytes() == b"new"
    assert (tmp_path / U.PREV_DIR / "pc_agent.py").read_bytes() == b"old"
    assert U.read_state(d)["pending_health"] is True and U.read_state(d)["seq"] == 6
    U.mark_healthy(d)
    assert U.read_state(d)["pending_health"] is False


@pytest.mark.parametrize("break_it", ["other_key", "tampered_file", "tampered_manifest", "old_seq", "same_seq", "bad_name"])
def test_a_bad_bundle_changes_nothing(key, tmp_path, break_it):
    d, n = str(tmp_path), int(key["n"], 16)
    (tmp_path / "pc_agent.py").write_bytes(b"old")
    U.write_state(d, {"seq": 5})
    seq, files = 6, {"pc_agent.py": b"evil"}
    if break_it == "old_seq":
        seq = 4
    if break_it == "same_seq":
        seq = 5
    if break_it == "bad_name":
        files = {"..\\..\\evil.py": b"evil"}
    b = bundle(make_bundle.new_key() if break_it == "other_key" else key, seq, files)
    if break_it == "tampered_file":
        b["files"]["pc_agent.py"] = base64.b64encode(b"worse").decode()
    if break_it == "tampered_manifest":
        b["manifest"]["seq"] = 7
    with pytest.raises(U.BundleRefused):
        U.apply_bundle(d, b, n)
    assert (tmp_path / "pc_agent.py").read_bytes() == b"old" and U.read_state(d)["seq"] == 5
    assert not (tmp_path / "evil.py").exists()


def test_roll_back_restores_and_that_bundle_is_never_taken_again(key, tmp_path):
    d, n = str(tmp_path), int(key["n"], 16)
    (tmp_path / "pc_agent.py").write_bytes(b"old")
    U.write_state(d, {"seq": 5, "id": "b5"})
    U.apply_bundle(d, bundle(key, 6, {"pc_agent.py": b"crashes", "new_file.py": b"x"}), n)
    assert U.rollback(d) is True
    assert (tmp_path / "pc_agent.py").read_bytes() == b"old" and not (tmp_path / "new_file.py").exists()
    st = U.read_state(d)
    assert st["seq"] == 5 and st["bad_seq"] == 6 and not st.get("pending_health")
    assert not U.wanted(st, 6) and U.wanted(st, 7)
    with pytest.raises(U.BundleRefused):
        U.apply_bundle(d, bundle(key, 6, {"pc_agent.py": b"crashes"}), n)


class Run:
    """Stands in for subprocess.Popen: every start returns the next exit code."""
    def __init__(self, codes, on_start=None):
        self.codes, self.starts, self.on_start = list(codes), [], on_start

    def __call__(self, cmd, **kw):
        self.starts.append(cmd)
        self.kw = kw
        if self.on_start:
            self.on_start(len(self.starts))
        code = self.codes.pop(0)
        return SimpleNamespace(wait=lambda: code)


def test_supervisor_restarts_a_crash_and_after_an_update_and_leaves_for_a_second_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_boot, "HERE", str(tmp_path))
    monkeypatch.setattr(agent_boot, "TEMP", str(tmp_path))
    U.write_state(str(tmp_path), {"seq": 5})
    waits = []
    run = Run([1, U.EXIT_UPDATED, 1, 0])
    agent_boot.agent_loop(str(tmp_path), ["--device", "PC_X"], spawn=run, sleep=waits.append)
    assert len(run.starts) == 4 and "--supervised" in run.starts[0] and run.starts[0][-1] == "PC_X"
    # a child of pythonw must get a real log: without it its prints die in a dead pipe (found by the kit simulation)
    assert run.kw["stdout"] is not None and "-u" in run.starts[0] and "utf8" in run.starts[0]
    assert len(waits) == 2                                  # the two crashes waited; the update restarted at once


def test_supervisor_rolls_back_a_new_version_that_dies_before_reporting(key, tmp_path, monkeypatch):
    monkeypatch.setattr(agent_boot, "HERE", str(tmp_path))
    monkeypatch.setattr(agent_boot, "TEMP", str(tmp_path))
    (tmp_path / "pc_agent.py").write_bytes(b"old")
    U.write_state(str(tmp_path), {"seq": 5})
    U.apply_bundle(str(tmp_path), bundle(key, 6, {"pc_agent.py": b"crashes"}), int(key["n"], 16))
    run = Run([1, 0])
    agent_boot.agent_loop(str(tmp_path), [], spawn=run, sleep=lambda s: None)
    assert (tmp_path / "pc_agent.py").read_bytes() == b"old" and U.read_state(str(tmp_path))["bad_seq"] == 6
    assert len(run.starts) == 2


def test_supervisor_log_rotation_keeps_one_old_copy(tmp_path, monkeypatch):
    log = tmp_path / "a.log"
    log.write_bytes(b"x" * 20)
    monkeypatch.setattr(agent_boot, "LOG_MAX", 10)
    agent_boot.rotate(str(log))
    assert not log.exists() and (tmp_path / "a.log.1").stat().st_size == 20
    agent_boot.rotate(str(log))                             # nothing there: no error


def test_enrollment_waits_for_the_portal_then_saves_the_key_and_removes_the_code(tmp_path):
    code, kf = tmp_path / "enroll.key", tmp_path / "device.key"
    code.write_text("the-code", encoding="utf-8")
    seen, answers = [], [OSError("relay not up"), SimpleNamespace(status_code=404),
                         SimpleNamespace(status_code=200, json=lambda: {"device_key": "own-key"})]

    def post(url, headers, json, timeout):
        seen.append((url, headers["X-Enroll-Key"], json["device_uid"]))
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    sleeps = []
    assert A.enroll("http://p/api", "PC_X", "LAB_01", str(code), str(kf), post=post, sleep=sleeps.append) == "own-key"
    assert A.read_key(str(kf)) == "own-key" and not code.exists()
    assert seen[0] == ("http://p/api/equipment/pc/enroll", "the-code", "PC_X") and len(sleeps) == 2


def test_a_share_viewer_gets_new_pictures_only_and_renews_its_token(monkeypatch):
    calls = []

    class Fake:
        def __init__(self):
            self.headers = {}

        def get(self, url, params=None, headers=None, timeout=None):
            calls.append((url.rsplit("/", 1)[-1], (headers or {}).get("If-None-Match")))
            if url.endswith("watch-token"):
                return SimpleNamespace(status_code=200, json=lambda: {"token": "t"})
            n = sum(1 for c in calls if c[0] == "frame.jpg")
            if n == 1:
                return SimpleNamespace(status_code=200, content=b"\xff\xd8a", headers={"ETag": '"1"'})
            if n == 2:
                return SimpleNamespace(status_code=304, content=b"", headers={})
            return SimpleNamespace(status_code=401, content=b"", headers={})
    monkeypatch.setattr(A.requests, "Session", Fake)
    fetch = A.share_fetcher("k", "http://p/api")
    assert fetch() == b"\xff\xd8a"
    assert fetch() is None and calls[-1] == ("frame.jpg", '"1"')
    assert fetch() is None                                   # expired token ...
    fetch()
    assert sum(1 for c in calls if c[0] == "watch-token") == 2   # ... asked for again


def test_make_bundle_files_all_exist():
    here = os.path.dirname(os.path.abspath(__file__))
    for name in make_bundle.FILES:
        assert os.path.isfile(os.path.join(here, name)), name
    json.dumps(make_bundle.FILES)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")
def test_keys_are_stored_with_dpapi_and_old_plain_files_are_converted(tmp_path):
    kf = tmp_path / "device.key"
    A.write_secret(str(kf), "own-key")
    assert "own-key" not in kf.read_text() and kf.read_text().startswith(A.DPAPI_PREFIX)
    assert A.read_key(str(kf)) == "own-key"
    old = tmp_path / "old" / "device.key"
    old.parent.mkdir()
    old.write_text("plain-key")
    assert A.read_key(str(old)) == "plain-key"
    assert "plain-key" not in old.read_text()                 # protected on first read
    assert A.read_key(str(old)) == "plain-key"


def test_a_damaged_protected_key_is_refused_not_used(tmp_path):
    kf = tmp_path / "device.key"
    kf.write_text(A.DPAPI_PREFIX + "bm90IGEgYmxvYg==")
    assert A.read_key(str(kf)) == ""


def test_the_account_id_does_not_name_the_account(monkeypatch):
    monkeypatch.setenv("USERDOMAIN", "GIU")
    monkeypatch.setenv("USERNAME", "somebody")
    a = A.account_id()
    assert "somebody" not in a and len(a) == 32
    monkeypatch.setenv("USERNAME", "other")
    assert A.account_id() != a


def test_second_account_waits_for_the_first_to_sign_out(tmp_path):
    runs, waits = [], []
    class P:
        def __init__(self, rc): self.rc = rc
        def wait(self): return self.rc
    seq = [0, 0, 75]
    def run(*a, **k):
        runs.append(1)
        if not seq: raise SystemExit
        return P(seq.pop(0))
    with pytest.raises(SystemExit):
        agent_boot.agent_loop(str(tmp_path), [], spawn=run, sleep=waits.append, wait_for_other=True)
    assert waits[:2] == [60, 60] and len(runs) == 4


def test_status_file_round_trip_and_tooltip_fits(tmp_path):
    import status_tray as T
    f = tmp_path / "s.txt"
    T.write_state("viewed", str(f))
    assert T.read_state(str(f)) == "viewed"
    f.write_text("nonsense")
    assert T.read_state(str(f)) == "starting"
    assert len(T.tooltip("viewed", "PC_" + "X" * 200)) <= 127
