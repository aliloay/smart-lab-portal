"""/api/health "version" (2026-11-18 integration fix): the stamp comes from the image's build args.

Before, a git-ignored app/build_info.json from 28 Oct (1be41ab) was copied into every hand-built image, so newer
images reported an old version. Now .dockerignore keeps the file out and the Dockerfile turns
--build-arg BUILD_COMMIT/BUILD_TIME into SMARTLAB_BUILD_COMMIT/SMARTLAB_BUILD_TIME."""
import os

from app import main


def _fresh(monkeypatch, **env):
    for k in ("SMARTLAB_BUILD_COMMIT", "SMARTLAB_BUILD_TIME"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(main, "_BUILD", None)


def test_build_args_win_over_a_stale_stamp_file(monkeypatch):
    _fresh(monkeypatch, SMARTLAB_BUILD_COMMIT="c49fa07", SMARTLAB_BUILD_TIME="20261118010203")
    v = main._build_info()
    assert v["id"] == "c49fa07-20261118010203" and v["commit"] == "c49fa07" and v["source"] == "image build args"


def test_without_build_args_the_version_says_unstamped_or_dev_mount(monkeypatch):
    _fresh(monkeypatch)
    v = main._build_info()
    stamp_file = os.path.join(os.path.dirname(main.__file__), "build_info.json")
    if os.path.exists(stamp_file):
        assert v["source"].startswith("build_info.json")
    else:
        assert v["id"] == "unstamped" and "BUILD_COMMIT" in v["note"]


def test_health_reports_the_stamp(client, monkeypatch):
    _fresh(monkeypatch, SMARTLAB_BUILD_COMMIT="abc1234")
    body = client.get("/api/health").json()
    assert body["version"]["id"] == "abc1234" and body["version"]["built_at"] is None


def test_dockerignore_keeps_the_local_stamp_file_out_of_the_image():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, ".dockerignore"), encoding="utf-8") as f:
        assert "app/build_info.json" in [ln.strip() for ln in f]
