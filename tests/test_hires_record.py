"""The full-resolution frame record (episode_NNN/hires/).

The purple adapter keeps every observation's frame exactly as the green agent sent it,
named by step, beside memory/ -- for a video of the life. Two things must hold: the bytes
are the wire bytes (no re-encode), and the model never learns the record exists (nothing
under mcu_worldmodel/ names it; it is outside the model's working directory).
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import pytest

MCU = Path(__file__).resolve().parents[1] / "MCU"
if str(MCU) not in sys.path:
    sys.path.insert(0, str(MCU))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
adapter = pytest.importorskip("worldmodel_purple_agent")


def _frame(fmt: str) -> tuple[str, bytes]:
    arr = np.zeros((360, 640, 3), dtype=np.uint8)
    arr[100:200, 300:400] = (30, 200, 90)
    ok, buf = cv2.imencode(fmt, arr)
    assert ok
    raw = buf.tobytes()
    return base64.b64encode(raw).decode(), raw


def _executor(tmp_path: Path, every: int = 1):
    ex = adapter.WorldModelExecutor.__new__(adapter.WorldModelExecutor)
    ex._hires_dir = tmp_path / "episode_001" / "hires"
    ex._hires_dir.mkdir(parents=True)
    ex._hires_failed = False
    ex.hires_every = every
    ex._step = 0
    return ex


def test_wire_bytes_are_kept_verbatim(tmp_path):
    enc, raw = _frame(".jpeg")
    data, ext = adapter.WorldModelExecutor.wire_frame_bytes(enc)
    assert (data, ext) == (raw, ".jpg")
    ex = _executor(tmp_path)
    ex._step = 17
    ex._keep_hires(enc)
    out = ex._hires_dir / "0000017.jpg"
    assert out.read_bytes() == raw
    # and it decodes to the render size
    assert cv2.imdecode(np.frombuffer(out.read_bytes(), np.uint8), cv2.IMREAD_COLOR).shape == (360, 640, 3)


def test_png_and_junk():
    enc, raw = _frame(".png")
    assert adapter.WorldModelExecutor.wire_frame_bytes(enc) == (raw, ".png")
    with pytest.raises(ValueError):
        adapter.WorldModelExecutor.wire_frame_bytes(base64.b64encode(b"not an image").decode())


def test_a_failure_stops_the_record_without_raising(tmp_path):
    ex = _executor(tmp_path)
    good, _ = _frame(".jpeg")
    ex._step = 1
    ex._keep_hires(good)
    ex._step = 2
    ex._keep_hires(base64.b64encode(b"junk").decode())  # must not raise
    assert ex._hires_failed
    ex._step = 3
    ex._keep_hires(good)
    assert sorted(p.name for p in ex._hires_dir.iterdir()) == ["0000001.jpg"]


def test_the_record_is_outside_the_model_tree_and_unnamed():
    # Beside memory/, never inside it: the model's cwd is episode_NNN/memory.
    src = (MCU / "worldmodel_purple_agent.py").read_text()
    assert 'workspace / "hires"' in src
    assert 'memory" / "hires' not in src and "memory/hires" not in src
    # Nothing the model reads names it: no prompt, skill, tool text or procedure under
    # mcu_worldmodel/ mentions the record.
    hits = subprocess.run(
        ["grep", "-rl", "-i", "hires", str(MCU / "mcu_worldmodel")],
        capture_output=True, text=True,
    ).stdout.split()
    assert hits == [], hits
