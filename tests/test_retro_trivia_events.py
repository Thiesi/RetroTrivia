"""Game events for NetBBS (door API 5, issue #20): a perfect round is reported
as one request in the outbound drop directory, and nothing at all is written
unless `door_info.json` carries `outbound.events`."""

import contextlib
import io
import json

import pytest

from .test_retro_trivia import _load

rt = _load()

_EVENTS = {"types": ["rank", "achievement", "medal", "capture", "perfect"],
           "events_per_hour": 12, "title_max": 80, "standings_rows": 10}


def door_info(tmp_path, monkeypatch, *, events=True, outbound=True, user_id=12, **extra):
    """A NetBBS launch: `door_info.json` beside the drop directory NetBBS made."""
    (tmp_path / "outbound").mkdir()
    info = {"door_api": 5, "handle": "Mara", "user_id": user_id, "node_name": "Test BBS", **extra}
    if outbound:
        info["outbound"] = {"label": "RetroTrivia.door", "directory": "outbound",
                            "results": str(tmp_path / "results"), "boards": [], "posts_per_hour": 6}
        if events:
            info["outbound"]["events"] = dict(_EVENTS)
    path = tmp_path / "door_info.json"
    path.write_text(json.dumps(info), encoding="utf-8")
    monkeypatch.setenv("NETBBS_DOOR_INFO", str(path))
    return rt._load_door_info()


def requests(tmp_path):
    return sorted((tmp_path / "outbound").iterdir())


def test_a_perfect_round_drops_one_event_request(tmp_path, monkeypatch):
    info = door_info(tmp_path, monkeypatch)
    assert rt.report_perfect_round(info, 5, 5)
    [request] = requests(tmp_path)
    assert request.suffix == ".json"
    assert json.loads(request.read_text(encoding="utf-8")) == {"event": {"type": "perfect", "user_id": 12}}
    assert len(request.read_bytes()) <= 2048


def test_request_names_sort_in_the_order_they_were_written(tmp_path, monkeypatch):
    info = door_info(tmp_path, monkeypatch)
    clock = iter([9, 10])
    monkeypatch.setattr(rt.time, "time_ns", lambda: next(clock))
    assert rt.report_perfect_round(info, 3, 3) and rt.report_perfect_round(info, 3, 3)
    assert [path.name for path in requests(tmp_path)] == [
        "perfect-00000000000000000009.json", "perfect-00000000000000000010.json"]


@pytest.mark.parametrize("score,total", [(4, 5), (0, 5), (0, 0)])
def test_only_a_perfect_round_is_reported(tmp_path, monkeypatch, score, total):
    info = door_info(tmp_path, monkeypatch)
    assert not rt.report_perfect_round(info, score, total)
    assert requests(tmp_path) == []


@pytest.mark.parametrize("setup", [
    {"events": False}, {"outbound": False}, {"user_id": 0}, {"user_id": None}, {"user_id": "12"},
])
def test_nothing_is_written_without_events_or_a_caller(tmp_path, monkeypatch, setup):
    info = door_info(tmp_path, monkeypatch, **setup)
    assert not rt.report_perfect_round(info, 5, 5)
    assert requests(tmp_path) == []


def test_nothing_is_written_when_perfect_is_not_an_offered_type(tmp_path, monkeypatch):
    info = door_info(tmp_path, monkeypatch)
    info["outbound"]["events"]["types"] = ["rank"]
    assert not rt.report_perfect_round(info, 5, 5)
    assert requests(tmp_path) == []


def test_a_classic_host_never_reports(tmp_path, monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    info = {"user_id": 12, "outbound": {"directory": "outbound", "events": dict(_EVENTS)}}
    assert not rt.report_perfect_round(info, 5, 5)


def test_a_missing_drop_directory_does_not_break_the_round(tmp_path, monkeypatch):
    info = door_info(tmp_path, monkeypatch)
    (tmp_path / "outbound").rmdir()
    assert not rt.report_perfect_round(info, 5, 5)


def _play(monkeypatch, info, answers):
    """Play a round in process, answering each question as `answers` says:
    True right, False wrong, None to quit."""
    right = {question: choices[index] for question, choices, index in rt.QUESTIONS}
    plan = iter(answers)

    def ask(p, number, total, question, choices, width=78, record=None):
        answer = next(plan)
        if answer is None:
            return None
        index = choices.index(right[question])
        return index if answer else (index + 1) % len(choices)

    monkeypatch.setattr(rt, "ask_round_length", lambda p, width=78: len(answers))
    monkeypatch.setattr(rt, "ask_question", ask)
    monkeypatch.setattr(rt, "read_key", lambda: "x")
    with contextlib.redirect_stdout(io.StringIO()):
        assert rt._play_round(info) == 0


def test_a_perfect_round_played_through_is_reported_once(tmp_path, monkeypatch):
    _play(monkeypatch, door_info(tmp_path, monkeypatch), [True, True, True])
    [request] = requests(tmp_path)
    assert json.loads(request.read_text(encoding="utf-8"))["event"] == {"type": "perfect", "user_id": 12}


@pytest.mark.parametrize("answers", [[True, False, True], [True, None, True]])
def test_a_missed_or_abandoned_round_is_not_reported(tmp_path, monkeypatch, answers):
    _play(monkeypatch, door_info(tmp_path, monkeypatch), answers)
    assert requests(tmp_path) == []
