"""The quota guard: a job whose Claude arms spend a subscription stops before the account is
out, instead of playing refused turns as no-ops (MCU/scripts/quota_guard.py)."""
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("quota_guard", ROOT / "MCU" / "scripts" / "quota_guard.py")
qg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qg)


def _info(status="allowed", five=0.2, seven=0.3, kind="five_hour"):
    return {"status": status, "rateLimitType": kind, "resetsAt": 1791154200,
            "unifiedWindows": {"five_hour": {"utilization": five, "resetsAt": 1},
                               "seven_day": {"utilization": seven, "resetsAt": 2}}}


def _turn(root, arm, n, info, mtime=None):
    d = root / arm / "episode_001" / "codex_turns"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"turn_{n:04d}.events.jsonl"
    lines = [{"type": "system", "subtype": "init"}]
    if info is not None:
        lines.append({"type": "rate_limit_event", "rate_limit_info": info})
    lines.append({"type": "result", "is_error": False})
    p.write_text("".join(json.dumps(x) + "\n" for x in lines))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def test_a_refused_turn_always_stops_the_job():
    why = qg.verdict(_info(status="rejected", five=0.0, seven=1.0, kind="seven_day"))
    assert why and "refused" in why and "seven_day" in why


def test_without_caps_a_nearly_full_window_does_not_stop_it():
    # the dedicated arm account ran its valid lives at 91-95% of the week
    assert qg.verdict(_info(status="allowed_warning", five=0.3, seven=0.95)) is None


def test_caps_stop_it_at_the_cap_and_not_below():
    assert qg.verdict(_info(five=0.79, seven=0.5), cap_5h=0.80, cap_7d=0.75) is None
    assert "5-hour" in qg.verdict(_info(five=0.80, seven=0.5), cap_5h=0.80, cap_7d=0.75)
    assert "7-day" in qg.verdict(_info(five=0.10, seven=0.75), cap_5h=0.80, cap_7d=0.75)


def test_a_record_without_the_window_table_is_read_from_its_own_fields():
    info = {"status": "allowed_warning", "rateLimitType": "seven_day", "utilization": 0.91}
    assert qg.windows(info) == {"seven_day": 0.91}
    assert "7-day" in qg.verdict(info, cap_7d=0.9)


def test_only_lives_written_since_the_guard_started_count(tmp_path):
    now = time.time()
    # an earlier life of the same prefix, on another account, at 99% of its week
    _turn(tmp_path, "sr3l_blaze_tail_none", 19, _info(status="allowed_warning", seven=0.99), mtime=now - 7200)
    assert qg.newest_event(str(tmp_path), "sr3l", now - 60) is None
    _turn(tmp_path, "sr3l_enderman_tail_none", 1, _info(five=0.2, seven=0.3), mtime=now - 30)
    _turn(tmp_path, "sr3l_enderman_tail_none", 2, None, mtime=now - 10)          # a turn with no record
    _turn(tmp_path, "other_arm", 1, _info(status="rejected"), mtime=now - 5)      # not this prefix
    path, info = qg.newest_event(str(tmp_path), "sr3l", now - 60)
    assert path.endswith("turn_0001.events.jsonl") and info["status"] == "allowed"


def test_once_reports_the_stop_and_writes_the_marker_without_cancelling(tmp_path, capsys):
    now = time.time()
    _turn(tmp_path, "sr3l_enderman_tail_none", 7, _info(five=0.86, seven=0.4), mtime=now)
    marker = tmp_path / "stop.json"
    rc = qg.main(["--root", str(tmp_path), "--prefix", "sr3l", "--cap-5h", "0.80", "--since", str(now - 60),
                  "--marker", str(marker), "--job", "12345", "--once"])
    assert rc == 3
    rec = json.loads(marker.read_text())
    assert rec["job"] == "12345" and "5-hour" in rec["why"] and rec["windows"]["five_hour"] == 0.86
    assert "QUOTA STOP" in capsys.readouterr().out
    # and a healthy account is left alone
    _turn(tmp_path, "sr3l_enderman_tail_none", 8, _info(five=0.5, seven=0.4), mtime=now + 1)
    assert qg.main(["--root", str(tmp_path), "--prefix", "sr3l", "--cap-5h", "0.80",
                    "--since", str(now - 60), "--once"]) == 0
