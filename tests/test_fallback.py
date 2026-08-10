"""heuristic_bucket() and infer_outcome(): the always-succeeds fallback."""

from datetime import datetime, timedelta, timezone

from mimir import Outcome
from mimir_ingest.fallback import heuristic_bucket, infer_outcome
from mimir_ingest.models import Episode, ToolCall, Turn

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def episode_of(*texts: str, tool_names: tuple[str, ...] = ()) -> Episode:
    turns = [
        Turn(role="user", text=t, timestamp=BASE + timedelta(minutes=i))
        for i, t in enumerate(texts)
    ]
    if tool_names:
        turns.append(
            Turn(
                role="assistant",
                text="",
                timestamp=BASE + timedelta(minutes=len(texts)),
                tool_calls=[ToolCall(name=n, preview="") for n in tool_names],
            )
        )
    return Episode(source="claude-code", session_id="s1", turns=turns)


def test_fix_keywords_bucket_as_fix():
    assert heuristic_bucket(episode_of("there is a bug in the login flow")).category == "fix"


def test_feature_keywords_bucket_as_feature():
    assert heuristic_bucket(episode_of("add a new export button")).category == "feature"


def test_refactor_keywords_bucket_as_refactor():
    assert heuristic_bucket(episode_of("refactor the auth module")).category == "refactor"


def test_no_signal_falls_back_to_other():
    assert heuristic_bucket(episode_of("what time is it")).category == "other"


def test_task_is_the_first_user_message():
    bucketed = heuristic_bucket(episode_of("fix the flaky test", "some other later text"))
    assert bucketed.task == "fix the flaky test"


def test_action_names_the_tools_used():
    bucketed = heuristic_bucket(episode_of("fix it", tool_names=("Edit", "Bash")))
    assert "Edit" in bucketed.action and "Bash" in bucketed.action


def test_action_notes_discussion_only_when_no_tools():
    bucketed = heuristic_bucket(episode_of("just talking"))
    assert "discussion only" in bucketed.action


def test_heuristic_bucket_always_sets_an_outcome():
    assert heuristic_bucket(episode_of("anything")).outcome is not None


def test_infer_outcome_reads_positive_reaction():
    assert infer_outcome(episode_of("fix the bug", "thanks, works now")) is Outcome.SUCCESS


def test_infer_outcome_reads_negative_reaction():
    assert infer_outcome(episode_of("fix the bug", "still broken")) is Outcome.FAILURE


def test_infer_outcome_defaults_to_partial_when_ambiguous():
    assert infer_outcome(episode_of("fix the bug", "ok let's move on")) is Outcome.PARTIAL
