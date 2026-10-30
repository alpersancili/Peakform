from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal

from .generation import generate_plan_days, suggest_progression
from .models import (
    Exercise,
    ExerciseLog,
    RecoveryNote,
    SessionStatus,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)


def make_exercise(name, category, movement_type="reps", difficulty=ExperienceLevel.BEGINNER,
                   equipment=None, goals=None, reps=10, hold=None, rest=60):
    return Exercise.objects.create(
        name=name, category=category, movement_type=movement_type, difficulty_level=difficulty,
        equipment_required=equipment or [], primary_goal_tags=goals or [],
        instructions="Do it with good form.", default_rest_seconds=rest,
        default_sets=3, default_reps=reps if movement_type == "reps" else None,
        default_hold_seconds=hold if movement_type == "hold" else None,
    )


class GenerationTests(TestCase):
    def setUp(self):
        self.warmup = make_exercise("Warmup A", "warmup")
        self.cooldown = make_exercise("Cooldown A", "cooldown")
        self.push_beginner = make_exercise("Easy Push", "push", difficulty=ExperienceLevel.BEGINNER)
        self.push_advanced = make_exercise("Hard Push", "push", difficulty=ExperienceLevel.ADVANCED)
        self.pull_needs_bar = make_exercise("Pull-up", "pull", equipment=[Equipment.PULL_UP_BAR])
        self.pull_bodyweight = make_exercise("Table Row", "pull")
        self.legs = make_exercise("Squat", "legs")
        self.core = make_exercise("Plank", "core", movement_type="hold", hold=30)
        self.skill_tagged = make_exercise(
            "Handstand", "skill", movement_type="hold", hold=20,
            difficulty=ExperienceLevel.ADVANCED, goals=[PrimaryGoal.SKILLS],
        )
        self.all_exercises = list(Exercise.objects.all())

    def test_training_days_capped_at_six(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 7, 45)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertEqual(len(training_days), 6)
        self.assertTrue(days[6].is_rest_day)

    def test_three_day_plan_has_four_rest_days(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45)
        rest_days = [d for d in days if d.is_rest_day]
        self.assertEqual(len(rest_days), 4)

    def test_equipment_filtering_excludes_unavailable_equipment(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.GENERAL_FITNESS, 3, 60)
        selected_names = {pe.exercise.name for d in days for pe in d.exercises}
        self.assertNotIn("Pull-up", selected_names)
        self.assertIn("Table Row", selected_names)

    def test_equipment_filtering_includes_when_available(self):
        days = generate_plan_days(
            self.all_exercises, ExperienceLevel.ADVANCED, [Equipment.PULL_UP_BAR], PrimaryGoal.GENERAL_FITNESS, 3, 60
        )
        selected_names = {pe.exercise.name for d in days for pe in d.exercises}
        self.assertIn("Pull-up", selected_names)

    def test_experience_filtering_excludes_harder_exercises(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 60)
        selected_names = {pe.exercise.name for d in days for pe in d.exercises}
        self.assertNotIn("Hard Push", selected_names)
        self.assertNotIn("Handstand", selected_names)

    def test_advanced_user_can_get_harder_exercises(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.GENERAL_FITNESS, 3, 60)
        selected_names = {pe.exercise.name for d in days for pe in d.exercises}
        self.assertIn("Hard Push", selected_names)

    def test_goal_tagged_exercise_prioritized_for_matching_goal(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 1, 90)
        day = days[0]
        names_in_order = [pe.exercise.name for pe in day.exercises]
        # Skill-tagged exercise should appear (goal-matched) ahead of equally-valid non-tagged ones.
        self.assertIn("Handstand", names_in_order)

    def test_every_training_day_includes_warmup_and_cooldown(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 2, 45)
        for day in days:
            if day.is_rest_day:
                continue
            names = [pe.exercise.name for pe in day.exercises]
            self.assertIn("Warmup A", names)
            self.assertIn("Cooldown A", names)


class ProgressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.exercise_reps = make_exercise("Push-up", "push", reps=10)
        self.exercise_hold = make_exercise("Plank", "core", movement_type="hold", hold=30)
        plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45,
        )
        self.plan_day = WorkoutPlanDay.objects.create(plan=plan, day_index=0, label="Full Body")
        self.pe_reps = WorkoutPlanExercise.objects.create(
            plan_day=self.plan_day, exercise=self.exercise_reps, target_sets=3, target_reps=10, rest_seconds=60
        )
        self.pe_hold = WorkoutPlanExercise.objects.create(
            plan_day=self.plan_day, exercise=self.exercise_hold, target_sets=3, target_hold_seconds=30, rest_seconds=45
        )
        self.session = WorkoutSession.objects.create(user=self.user, plan_day=self.plan_day)

    def _log(self, exercise, set_number, reps=None, hold_seconds=None, rpe=None):
        return ExerciseLog.objects.create(
            session=self.session, exercise=exercise, set_number=set_number,
            reps=reps, hold_seconds=hold_seconds, effort_rpe=rpe,
        )

    def test_no_logs_holds_target(self):
        suggestion = suggest_progression(self.pe_reps, [])
        self.assertEqual(suggestion.direction, "hold")
        self.assertEqual(suggestion.new_target_reps, 10)

    def test_met_target_with_low_rpe_increases(self):
        logs = [self._log(self.exercise_reps, i, reps=10, rpe=5) for i in range(1, 4)]
        suggestion = suggest_progression(self.pe_reps, logs)
        self.assertEqual(suggestion.direction, "increase")
        self.assertEqual(suggestion.new_target_reps, 11)

    def test_high_rpe_decreases_even_if_target_met(self):
        logs = [self._log(self.exercise_reps, i, reps=10, rpe=9) for i in range(1, 4)]
        suggestion = suggest_progression(self.pe_reps, logs)
        self.assertEqual(suggestion.direction, "decrease")
        self.assertEqual(suggestion.new_target_reps, 9)

    def test_missed_target_holds(self):
        logs = [self._log(self.exercise_reps, i, reps=7, rpe=7) for i in range(1, 4)]
        suggestion = suggest_progression(self.pe_reps, logs)
        self.assertEqual(suggestion.direction, "hold")
        self.assertEqual(suggestion.new_target_reps, 10)

    def test_hold_type_increments_seconds(self):
        logs = [self._log(self.exercise_hold, i, hold_seconds=30, rpe=5) for i in range(1, 4)]
        suggestion = suggest_progression(self.pe_hold, logs)
        self.assertEqual(suggestion.direction, "increase")
        self.assertEqual(suggestion.new_target_hold_seconds, 35)

    def test_decrease_never_drops_reps_below_one(self):
        self.pe_reps.target_reps = 1
        logs = [self._log(self.exercise_reps, 1, reps=1, rpe=10)]
        suggestion = suggest_progression(self.pe_reps, logs)
        self.assertEqual(suggestion.new_target_reps, 1)


class PlanGenerateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        make_exercise("Warmup A", "warmup")
        make_exercise("Cooldown A", "cooldown")
        make_exercise("Push-up", "push")
        make_exercise("Table Row", "pull")
        make_exercise("Squat", "legs")
        make_exercise("Plank", "core", movement_type="hold", hold=30)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("workouts:plan_generate"))
        self.assertEqual(response.status_code, 302)

    def test_generate_creates_active_plan_with_seven_days(self):
        response = self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45, "equipment": [],
        })
        self.assertRedirects(response, reverse("workouts:plan_overview"))
        plan = WorkoutPlan.objects.get(user=self.user)
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.days.count(), 7)

    def test_regenerating_deactivates_previous_plan(self):
        self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45, "equipment": [],
        })
        self.client.post(reverse("workouts:plan_generate"), {
            "goal": "strength", "experience_level": "beginner",
            "training_days_per_week": 4, "session_duration_minutes": 45, "equipment": [],
        })
        self.assertEqual(WorkoutPlan.objects.filter(user=self.user, is_active=True).count(), 1)
        self.assertEqual(WorkoutPlan.objects.filter(user=self.user).count(), 2)


class SessionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.exercise = make_exercise("Push-up", "push", reps=10)
        plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        self.training_day = WorkoutPlanDay.objects.create(plan=plan, day_index=0, label="Full Body")
        self.rest_day = WorkoutPlanDay.objects.create(plan=plan, day_index=1, label="Rest", is_rest_day=True)
        self.plan_exercise = WorkoutPlanExercise.objects.create(
            plan_day=self.training_day, exercise=self.exercise, target_sets=2, target_reps=10, rest_seconds=60
        )

    def test_starting_a_training_day_creates_session(self):
        response = self.client.post(reverse("workouts:session_start", args=[self.training_day.id]))
        session = WorkoutSession.objects.get(user=self.user)
        self.assertRedirects(response, reverse("workouts:session_detail", args=[session.id]))
        self.assertEqual(session.status, SessionStatus.IN_PROGRESS)

    def test_starting_rest_day_does_not_create_session(self):
        response = self.client.post(reverse("workouts:session_start", args=[self.rest_day.id]))
        self.assertRedirects(response, reverse("workouts:plan_overview"))
        self.assertFalse(WorkoutSession.objects.exists())

    def test_starting_same_day_twice_reuses_in_progress_session(self):
        self.client.post(reverse("workouts:session_start", args=[self.training_day.id]))
        self.client.post(reverse("workouts:session_start", args=[self.training_day.id]))
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 1)

    def test_log_set_increments_set_number(self):
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)
        self.client.post(
            reverse("workouts:log_set", args=[session.id, self.exercise.id]), {"reps": 10, "effort_rpe": 6}
        )
        self.client.post(
            reverse("workouts:log_set", args=[session.id, self.exercise.id]), {"reps": 9, "effort_rpe": 7}
        )
        logs = list(ExerciseLog.objects.filter(session=session).order_by("set_number"))
        self.assertEqual([l.set_number for l in logs], [1, 2])

    def test_cannot_log_set_for_another_users_session(self):
        other = User.objects.create_user("other", "o@example.com", "password123!")
        other_session = WorkoutSession.objects.create(user=other)
        response = self.client.post(
            reverse("workouts:log_set", args=[other_session.id, self.exercise.id]), {"reps": 5}
        )
        self.assertEqual(response.status_code, 404)

    def test_complete_session_applies_progression_and_sets_status(self):
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)
        ExerciseLog.objects.create(session=session, exercise=self.exercise, set_number=1, reps=10, effort_rpe=5)
        ExerciseLog.objects.create(session=session, exercise=self.exercise, set_number=2, reps=10, effort_rpe=5)

        self.client.post(reverse("workouts:session_complete", args=[session.id]), {"notes": "Felt good"})

        session.refresh_from_db()
        self.plan_exercise.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(session.notes, "Felt good")
        self.assertEqual(self.plan_exercise.target_reps, 11)


class RecoveryNoteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_saving_recovery_note_upserts_today(self):
        self.client.post(reverse("workouts:recovery_note_add"), {
            "sleep_quality": 4, "soreness": 2, "fatigue": 3, "notes": "Feeling fresh",
        })
        self.assertEqual(RecoveryNote.objects.filter(user=self.user).count(), 1)
        note = RecoveryNote.objects.get(user=self.user)
        self.assertEqual(note.sleep_quality, 4)

        self.client.post(reverse("workouts:recovery_note_add"), {
            "sleep_quality": 2, "soreness": 4, "fatigue": 4, "notes": "Rough night",
        })
        self.assertEqual(RecoveryNote.objects.filter(user=self.user).count(), 1)
        note.refresh_from_db()
        self.assertEqual(note.sleep_quality, 2)
