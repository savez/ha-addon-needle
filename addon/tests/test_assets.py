"""Test del download degli asset."""
import os

from app.assets import WEIGHTS_NAME, ensure_assets


def fake_run_factory(calls):
    def fake_run(cmd, check):
        calls.append(cmd)
        out = cmd[cmd.index("--out") + 1]
        os.makedirs(out, exist_ok=True)
        if cmd[1] == "download":
            open(os.path.join(out, WEIGHTS_NAME), "wb").close()
        else:
            open(os.path.join(out, "libneedle.so"), "wb").close()
    return fake_run


def test_downloads_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("NEEDLE3_LIB_PATH", raising=False)
    calls = []
    weights = ensure_assets(tmp_path, run=fake_run_factory(calls))
    assert weights == tmp_path / "weights" / WEIGHTS_NAME
    assert [c[1] for c in calls] == ["download", "fetch"]
    assert os.environ["NEEDLE3_LIB_PATH"] == str(tmp_path / "engine" / "libneedle.so")


def test_skips_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("NEEDLE3_LIB_PATH", raising=False)
    (tmp_path / "weights").mkdir()
    (tmp_path / "weights" / WEIGHTS_NAME).touch()
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "libneedle.so").touch()
    calls = []
    ensure_assets(tmp_path, run=fake_run_factory(calls))
    assert calls == []
    assert os.environ["NEEDLE3_LIB_PATH"].endswith("libneedle.so")
