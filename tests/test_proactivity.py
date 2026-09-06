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
    def test_single_observation_is_observed_once_and_never_strong(self):
        stage = habit_stage([Observation("open_ide@morning", 100.0)], signature="open_ide@morning")
        self.assertEqual(stage, "observed_once")
        self.assertFalse(suggestion_allowed(stage))

    def test_three_observations_become_possible_habit(self):
        observations = [Observation("open_ide@morning", day) for day in (1.0, 2.0, 3.0)]
        stage = habit_stage(observations, signature="open_ide@morning")
        self.assertEqual(stage, "possible_habit")
        self.assertTrue(suggestion_allowed(stage))  # suggestion, never execution

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
        self.assertEqual(habit_stage(observations, signature="open_ide@morning"), "observed_once")


class QuietHoursTests(unittest.TestCase):
    def test_wrap_around_window(self):
        quiet = QuietHours(tz_offset_minutes=0, start_minute=22 * 60, end_minute=7 * 60)
        # 2026-09-06 23:00 UTC -> quiet
        late = datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc).timestamp()
        morning = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc).timestamp()
        self.assertTrue(quiet.is_quiet(late))
        self.assertFalse(quiet.is_quiet(morning))

    def test_timezone_shifts_the_window(self):
        quiet = QuietHours(tz_offset_minutes=60, start_minute=22 * 60, end_minute=7 * 60)
        # 21:00 UTC = 22:00 local -> quiet begins
        edge = datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc).timestamp()
        self.assertTrue(quiet.is_quiet(edge))

    def test_channel_gating(self):
        quiet = QuietHours(allowed_channels=("ui",))
        self.assertTrue(quiet.channel_allowed("ui"))
        self.assertFalse(quiet.channel_allowed("voice"))


class WeeklyScheduleTests(unittest.TestCase):
    def test_weekly_next_due(self):
        # Monday 2026-09-07, 09:00 local (UTC+0)
        spec = SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=0)
        sunday = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc).timestamp()
        due = next_due(spec, now=sunday, last_run=None)
        local = datetime.fromtimestamp(due, tz=timezone.utc)
        self.assertEqual(local.weekday(), 0)  # Monday
        self.assertEqual(local.hour, 9)

    def test_weekly_avoids_double_fire_after_last_run(self):
        spec = SchedulerSpec(kind="weekly", weekly_weekday=0, daily_hour=9, daily_minute=0)
        monday_run = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc).timestamp()
        now = monday_run + 60
        due = next_due(spec, now=now, last_run=monday_run)
        local = datetime.fromtimestamp(due, tz=timezone.utc)
        self.assertEqual(local.weekday(), 0)
        self.assertEqual(local.day, 14)  # next Monday


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
