import unittest
from datetime import datetime, timezone

from tasks.model import Task, TaskState, TaskStep
from tasks.proactivity import (
    QuietHours,
    Observation,
    habit_stage,
    is_suggestion_ready,
    suggestion_allowed,
    task_evidence,
)
from tasks.scheduler import SchedulerSpec, next_due


def _step(name, state="done", outcome=None, verified=False):
    outcome = dict(outcome or {"ok": True})
    if verified:
        outcome["verified"] = True
    return TaskStep(name=name, action={}, idempotency_key=f"key-{name}", state=state, outcome=outcome)


def _task(steps, state=TaskState.COMPLETED, title="Relatório diário"):
    return Task(id="t1", owner_id="u1", title=title, steps=steps, state=state, created_at=1.0, updated_at=2.0)


class HabitLadderTests(unittest.TestCase):
    def test_no_observation_is_unobserved(self):
        self.assertEqual(habit_stage([], signature="open_ide@morning"), "unobserved")
        self.assertFalse(suggestion_allowed("unobserved"))

    def test_single_observation_is_observed_once_and_never_strong(self):
        stage = habit_stage([Observation("open_ide@morning", 100.0)], signature="open_ide@morning")
        self.assertEqual(stage, "observed_once")
        self.assertFalse(suggestion_allowed(stage))

    def test_three_observations_become_possible_habit(self):
        observations = [Observation("open_ide@morning", day) for day in (1.0, 2.0, 3.0)]
        stage = habit_stage(observations, signature="open_ide@morning")
        self.assertEqual(stage, "possible_habit")
        self.assertTrue(suggestion_allowed(stage))

    def test_five_observations_become_probable_habit(self):
        observations = [Observation("open_ide@morning", day) for day in range(5)]
        self.assertEqual(habit_stage(observations, signature="open_ide@morning"), "probable_habit")

    def test_approval_is_the_only_path_to_approved_routine(self):
        observations = [Observation("open_ide@morning", day) for day in range(10)]
        self.assertEqual(habit_stage(observations, signature="open_ide@morning"), "probable_habit")
        self.assertEqual(
            habit_stage(observations, signature="open_ide@morning", approved=True),
            "approved_routine",
        )

    def test_other_signatures_do_not_count(self):
        observations = [Observation("other", day) for day in range(10)]
        self.assertEqual(habit_stage(observations, signature="open_ide@morning"), "unobserved")

    def test_invalid_thresholds_fail_closed(self):
        with self.assertRaises(ValueError):
            habit_stage([], signature="x", min_occurrences_possible=1)
        with self.assertRaises(ValueError):
            habit_stage([], signature="x", min_occurrences_possible=5, min_occurrences_probable=3)


class QuietHoursTests(unittest.TestCase):
    def test_wrap_around_window(self):
        quiet = QuietHours(tz_offset_minutes=0, start_minute=22 * 60, end_minute=7 * 60)
        late = datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc).timestamp()
        morning = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc).timestamp()
        self.assertTrue(quiet.is_quiet(late))
        self.assertFalse(quiet.is_quiet(morning))

    def test_timezone_shifts_the_window(self):
        quiet = QuietHours(tz_offset_minutes=60, start_minute=22 * 60, end_minute=7 * 60)
        edge = datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc).timestamp()
        self.assertTrue(quiet.is_quiet(edge))

    def test_channel_gating(self):
        quiet = QuietHours(allowed_channels=("ui",))
        self.assertTrue(quiet.channel_allowed("ui"))
        self.assertFalse(quiet.channel_allowed("voice"))

    def test_equal_bounds_mean_no_quiet_window(self):
        quiet = QuietHours(start_minute=9 * 60, end_minute=9 * 60)
        noon = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc).timestamp()
        self.assertFalse(quiet.is_quiet(noon))

    def test_invalid_bounds_fail_closed(self):
        with self.assertRaises(ValueError):
            QuietHours(start_minute=-1)
        with self.assertRaises(ValueError):
            QuietHours(end_minute=24 * 60)


class WeeklyScheduleTests(unittest.TestCase):
    def test_weekly_next_due(self):
        spec = SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=0)
        sunday = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc).timestamp()
        due = next_due(spec, now=sunday, last_run=None)
        local = datetime.fromtimestamp(due, tz=timezone.utc)
        self.assertEqual(local.weekday(), 0)
        self.assertEqual(local.hour, 9)

    def test_weekly_exact_due_instant_is_not_skipped(self):
        spec = SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=0)
        monday = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(next_due(spec, now=monday, last_run=None), monday)

    def test_weekly_avoids_double_fire_after_last_run(self):
        spec = SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=0)
        monday_run = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc).timestamp()
        now = monday_run + 60
        due = next_due(spec, now=now, last_run=monday_run)
        local = datetime.fromtimestamp(due, tz=timezone.utc)
        self.assertEqual(local.weekday(), 0)
        self.assertEqual(local.day, 14)

    def test_invalid_weekday_or_minute_returns_none(self):
        now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc).timestamp()
        self.assertIsNone(next_due(SchedulerSpec(kind="weekly", weekly_weekday=7, daily_hour=9), now=now))
        self.assertIsNone(next_due(SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=60), now=now))


class TaskEvidenceTests(unittest.TestCase):
    def test_full_evidence_summary(self):
        task = _task([
            _step("abrir", verified=True),
            _step("verificar", outcome={"ok": True}),
            _step("falhou", state="failed", outcome={"ok": False, "error": "janela não apareceu"}),
            _step("pendente", state="pending"),
        ])
        evidence = task_evidence(task, cost=0.002, provider="gemini", model="flash")
        self.assertEqual(evidence["requested"], "Relatório diário")
        self.assertEqual(evidence["executed"], ["abrir", "verificar"])
        self.assertEqual(evidence["delivered"], 2)
        self.assertEqual(evidence["verified_steps"], 1)
        self.assertEqual(evidence["remaining"], ["pendente"])
        self.assertEqual(evidence["failures"], [{"step": "falhou", "error": "janela não apareceu"}])
        self.assertEqual(evidence["cost"], 0.002)
        self.assertEqual(evidence["provider"], "gemini")

    def test_cost_is_never_invented(self):
        task = _task([_step("a")])
        evidence = task_evidence(task)
        self.assertNotIn("cost", evidence)
        self.assertNotIn("provider", evidence)


class SuggestionGateTests(unittest.TestCase):
    def test_pending_tasks_are_suggestion_targets_never_auto_run(self):
        task = _task([_step("a", state="pending")], state=TaskState.AWAITING_APPROVAL)
        self.assertTrue(is_suggestion_ready(task))
        running = _task([_step("a")], state=TaskState.RUNNING)
        self.assertFalse(is_suggestion_ready(running))


if __name__ == "__main__":
    unittest.main()
