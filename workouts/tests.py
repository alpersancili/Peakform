from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal

from .ai_client import (
    WorkoutAIConfigurationError,
    WorkoutAIResponseError,
    generate_plan_with_ai,
)
from .ai_rate_limit import RateLimitExceeded, record_attempt_or_raise, requests_remaining_today
from .generation import generate_plan_days, suggest_progression
from .models import (
    Exercise,
    ExerciseLog,
    ProgramTemplate,
    ProgramTemplateDay,
    ProgramTemplateExercise,
    RecoveryNote,
    SessionStatus,
    SkillMilestone,
    WorkoutPlan,
    WorkoutPlanAIRequest,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)
from .personal_records import compute_personal_records, detect_new_records


def make_exercise(name, category, movement_type="reps", difficulty=ExperienceLevel.BEGINNER,
                   equipment=None, goals=None, reps=10, hold=None, rest=60):
    return Exercise.objects.create(
        name=name, category=category, movement_type=movement_type, difficulty_level=difficulty,
        equipment_required=equipment or [], primary_goal_tags=goals or [],
        instructions="Do it with good form.", default_rest_seconds=rest,
        default_sets=3, default_reps=reps if movement_type == "reps" else None,
        default_hold_seconds=hold if movement_type == "hold" else None,
    )


class ExerciseEmbedUrlTests(TestCase):
    def test_blank_video_url_gives_blank_embed_url(self):
        exercise = make_exercise("No Video", "core")
        self.assertEqual(exercise.embed_url, "")

    def test_standard_watch_url_converts_to_embed_url(self):
        exercise = make_exercise("Watch URL", "core")
        exercise.video_url = "https://www.youtube.com/watch?v=hne3nHGXPRM"
        self.assertEqual(exercise.embed_url, "https://www.youtube.com/embed/hne3nHGXPRM")

    def test_watch_url_with_extra_query_params_converts(self):
        exercise = make_exercise("Watch URL Extra", "core")
        exercise.video_url = "https://www.youtube.com/watch?v=hne3nHGXPRM&t=30s&list=PL123"
        self.assertEqual(exercise.embed_url, "https://www.youtube.com/embed/hne3nHGXPRM")

    def test_short_youtu_be_url_converts(self):
        exercise = make_exercise("Short URL", "core")
        exercise.video_url = "https://youtu.be/hne3nHGXPRM"
        self.assertEqual(exercise.embed_url, "https://www.youtube.com/embed/hne3nHGXPRM")

    def test_already_embed_url_passes_through_unchanged(self):
        exercise = make_exercise("Already Embed", "core")
        exercise.video_url = "https://www.youtube.com/embed/hne3nHGXPRM"
        self.assertEqual(exercise.embed_url, "https://www.youtube.com/embed/hne3nHGXPRM")

    def test_non_youtube_url_falls_back_unchanged(self):
        exercise = make_exercise("Other Host", "core")
        exercise.video_url = "https://example.com/videos/demo.mp4"
        self.assertEqual(exercise.embed_url, "https://example.com/videos/demo.mp4")


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
        self.pull_skill_tagged = make_exercise(
            "Front Lever Tuck", "pull", movement_type="hold", hold=10,
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

    def test_three_day_plan_spreads_training_days_instead_of_clustering(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45)
        training_indices = {d.day_index for d in days if not d.is_rest_day}
        self.assertEqual(training_indices, {0, 2, 4})

    def test_two_day_plan_spreads_training_days(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 2, 45)
        training_indices = {d.day_index for d in days if not d.is_rest_day}
        self.assertEqual(training_indices, {0, 3})

    def test_four_day_plan_spreads_training_days(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 4, 45)
        training_indices = {d.day_index for d in days if not d.is_rest_day}
        self.assertEqual(training_indices, {0, 1, 3, 4})

    def test_strength_goal_prescribes_fewer_reps_and_longer_rest(self):
        # Strength and General fitness both use a "Full Body" split at 1
        # day/week, so both sessions actually include push-category work
        # to compare (Endurance's 1-day split is pure Conditioning work
        # and intentionally never touches push/pull/legs at all).
        strength_days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.STRENGTH, 1, 90)
        general_days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 1, 90)

        strength_push = next(pe for pe in strength_days[0].exercises if pe.exercise.name == "Easy Push")
        general_push = next(pe for pe in general_days[0].exercises if pe.exercise.name == "Easy Push")

        self.assertLess(strength_push.target_reps, general_push.target_reps)
        self.assertGreater(strength_push.rest_seconds, general_push.rest_seconds)
        # Unscaled baseline for reference: both started from the same exercise default.
        self.assertEqual(self.push_beginner.default_reps, 10)
        self.assertEqual(strength_push.target_reps, 6)
        self.assertEqual(general_push.target_reps, 10)

    def test_warmup_and_cooldown_are_not_goal_scaled(self):
        strength_days = generate_plan_days(self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.STRENGTH, 1, 90)
        warmup = next(pe for pe in strength_days[0].exercises if pe.exercise.name == "Warmup A")
        self.assertEqual(warmup.target_reps, self.warmup.default_reps)
        self.assertEqual(warmup.rest_seconds, self.warmup.default_rest_seconds)

    def test_push_day_never_includes_pull_exercises(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 3, 90)
        push_day = next(d for d in days if d.label == "Push")
        categories = {pe.exercise.category for pe in push_day.exercises}
        self.assertNotIn("pull", categories)

    def test_pull_day_never_includes_push_exercises(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 3, 90)
        pull_day = next(d for d in days if d.label == "Pull")
        categories = {pe.exercise.category for pe in pull_day.exercises}
        self.assertNotIn("push", categories)

    def test_legs_day_includes_core_work(self):
        # Only Skills gets a dedicated "Legs" day at 3 days/week in the
        # goal-aware split (General fitness uses Full Body at 3 days).
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 3, 90)
        legs_day = next(d for d in days if d.label == "Legs")
        names = [pe.exercise.name for pe in legs_day.exercises]
        self.assertIn("Plank", names)

    def test_skill_category_never_added_to_pull_or_legs_days(self):
        # "Handstand" is push-dominant (skill category) - it should only
        # ever be eligible on a push-type day, never pull or legs, even
        # when the user's goal is Skills.
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 3, 90)
        pull_day = next(d for d in days if d.label == "Pull")
        legs_day = next(d for d in days if d.label == "Legs")
        self.assertNotIn("Handstand", [pe.exercise.name for pe in pull_day.exercises])
        self.assertNotIn("Handstand", [pe.exercise.name for pe in legs_day.exercises])

    def test_pull_dominant_skill_exercise_sequenced_first_on_pull_day(self):
        # Front Lever Tuck is catalogued as "pull" (it's also valid pure
        # pulling-strength work), not "skill" - but it's still skills-goal
        # tagged and should still go first on a pull day while fresh.
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 3, 90)
        pull_day = next(d for d in days if d.label == "Pull")
        main_exercises = [pe for pe in pull_day.exercises if pe.exercise.category not in ("warmup", "cooldown")]
        self.assertEqual(main_exercises[0].exercise.name, "Front Lever Tuck")

    def test_strength_goal_fits_fewer_exercises_than_general_fitness_in_same_duration(self):
        # Strength's longer rest (1.6x) and extra set per exercise take much
        # longer per exercise than general fitness's baseline (1.0x) rest -
        # packing the same exercise count into both would make a
        # "60-minute" strength session actually take well over two hours
        # of rest alone. Both use "Full Body" at 1 day/week so the pools
        # are directly comparable (Endurance's split is pure Conditioning
        # work, a different exercise pool entirely).
        strength_days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.STRENGTH, 1, 60)
        general_days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.GENERAL_FITNESS, 1, 60)

        strength_main = [pe for pe in strength_days[0].exercises if pe.exercise.category not in ("warmup", "cooldown")]
        general_main = [pe for pe in general_days[0].exercises if pe.exercise.category not in ("warmup", "cooldown")]
        self.assertLess(len(strength_main), len(general_main))

    def test_skill_exercise_sequenced_before_other_main_exercises(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 1, 90)
        day = days[0]
        main_exercises = [pe for pe in day.exercises if pe.exercise.category not in ("warmup", "cooldown")]
        self.assertEqual(main_exercises[0].exercise.name, "Handstand")

    def test_endurance_goal_uses_conditioning_not_push_pull_legs(self):
        conditioning = make_exercise("Burpee Test", "conditioning", reps=10)
        exercises = self.all_exercises + [conditioning]
        days = generate_plan_days(exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.ENDURANCE, 3, 60)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertTrue(all(d.label == "Conditioning" for d in training_days))
        categories = {pe.exercise.category for d in training_days for pe in d.exercises}
        self.assertEqual(categories - {"warmup", "cooldown"}, {"conditioning"})

    def test_flexibility_goal_uses_mobility_not_push_pull_legs(self):
        mobility = make_exercise("Hip Opener Test", "mobility", movement_type="hold", hold=30)
        exercises = self.all_exercises + [mobility]
        days = generate_plan_days(exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.FLEXIBILITY, 2, 45)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertTrue(all(d.label == "Mobility" for d in training_days))
        categories = {pe.exercise.category for d in training_days for pe in d.exercises}
        self.assertEqual(categories - {"warmup", "cooldown"}, {"mobility"})

    def test_skills_goal_gets_dedicated_push_pull_split_even_at_two_days(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.SKILLS, 2, 60)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertEqual([d.label for d in training_days], ["Push", "Pull"])

    def test_fat_loss_goal_alternates_full_body_and_conditioning(self):
        conditioning = make_exercise("Burpee Test", "conditioning", reps=10)
        exercises = self.all_exercises + [conditioning]
        days = generate_plan_days(exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.FAT_LOSS, 3, 60)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertEqual([d.label for d in training_days], ["Full Body", "Conditioning", "Full Body"])

    def test_strength_goal_uses_full_body_at_low_frequency_not_push_pull_legs(self):
        days = generate_plan_days(self.all_exercises, ExperienceLevel.ADVANCED, [], PrimaryGoal.STRENGTH, 3, 60)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertEqual([d.label for d in training_days], ["Full Body", "Full Body", "Full Body"])


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

    def test_no_equipment_is_exclusive_even_if_submitted_with_others(self):
        self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45,
            "equipment": ["none", "pull_up_bar", "rings"],
        })
        plan = WorkoutPlan.objects.get(user=self.user)
        self.assertEqual(plan.equipment, ["none"])


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

    def test_session_detail_shows_adjustable_rest_timer_with_recommended_default(self):
        self.client.post(reverse("workouts:session_start", args=[self.training_day.id]))
        session = WorkoutSession.objects.get(user=self.user)
        response = self.client.get(reverse("workouts:session_detail", args=[session.id]))
        self.assertContains(response, 'data-recommended-seconds="60"')
        self.assertContains(response, 'data-rest-seconds-input')
        self.assertContains(response, "Recommended: 60s")

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

    def test_substitute_swaps_in_the_easier_variation(self):
        easier = make_exercise("Knee Push-up", "push", reps=10)
        self.exercise.easier_variation = easier
        self.exercise.save()
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)

        response = self.client.post(
            reverse("workouts:substitute_exercise", args=[session.id, self.plan_exercise.id]),
            {"reason": "too_difficult"},
        )

        self.plan_exercise.refresh_from_db()
        self.assertRedirects(response, reverse("workouts:session_detail", args=[session.id]))
        self.assertEqual(self.plan_exercise.exercise, easier)

    def test_substitute_with_discomfort_shows_safety_warning(self):
        easier = make_exercise("Knee Push-up", "push", reps=10)
        self.exercise.easier_variation = easier
        self.exercise.save()
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)

        response = self.client.post(
            reverse("workouts:substitute_exercise", args=[session.id, self.plan_exercise.id]),
            {"reason": "discomfort"},
            follow=True,
        )
        self.assertContains(response, "stop and consider getting guidance")

    def test_substitute_without_easier_variation_leaves_exercise_unchanged(self):
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)

        response = self.client.post(
            reverse("workouts:substitute_exercise", args=[session.id, self.plan_exercise.id]),
            {"reason": "preference"},
            follow=True,
        )

        self.plan_exercise.refresh_from_db()
        self.assertEqual(self.plan_exercise.exercise, self.exercise)
        self.assertContains(response, "No substitute is set up")

    def test_cannot_substitute_exercise_in_another_users_plan(self):
        other = User.objects.create_user("other2", "o2@example.com", "password123!")
        other_plan = WorkoutPlan.objects.create(
            user=other, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        other_day = WorkoutPlanDay.objects.create(plan=other_plan, day_index=0, label="Full Body")
        other_plan_exercise = WorkoutPlanExercise.objects.create(
            plan_day=other_day, exercise=self.exercise, target_sets=2, target_reps=10, rest_seconds=60
        )
        session = WorkoutSession.objects.create(user=self.user, plan_day=self.training_day)

        response = self.client.post(
            reverse("workouts:substitute_exercise", args=[session.id, other_plan_exercise.id]),
            {"reason": "preference"},
        )
        self.assertEqual(response.status_code, 404)


class PersonalRecordsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.pushup = make_exercise("Push-up", "push", reps=10)
        self.plank = make_exercise("Plank", "core", movement_type="hold", hold=30)

    def _completed_session(self, *log_kwargs_list):
        session = WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        for index, kwargs in enumerate(log_kwargs_list, start=1):
            ExerciseLog.objects.create(session=session, set_number=index, **kwargs)
        return session

    def test_best_reps_set_wins_over_lower_sets(self):
        self._completed_session(
            {"exercise": self.pushup, "reps": 8}, {"exercise": self.pushup, "reps": 12}
        )
        records = compute_personal_records(self.user)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["exercise"], self.pushup)
        self.assertEqual(records[0]["value"], 12)

    def test_hold_exercise_tracked_by_hold_seconds(self):
        self._completed_session({"exercise": self.plank, "hold_seconds": 45})
        records = compute_personal_records(self.user)
        self.assertEqual(records[0]["value"], 45)
        self.assertEqual(records[0]["movement_type"], "hold")

    def test_in_progress_session_does_not_count(self):
        session = WorkoutSession.objects.create(user=self.user, status=SessionStatus.IN_PROGRESS)
        ExerciseLog.objects.create(session=session, exercise=self.pushup, set_number=1, reps=99)
        self.assertEqual(compute_personal_records(self.user), [])

    def test_detect_new_records_flags_improvement_over_prior_best(self):
        self._completed_session({"exercise": self.pushup, "reps": 10})
        new_session = self._completed_session({"exercise": self.pushup, "reps": 15})

        new_records = detect_new_records(self.user, new_session)
        self.assertEqual(new_records, [(self.pushup, 15)])

    def test_detect_new_records_excludes_non_improvements(self):
        self._completed_session({"exercise": self.pushup, "reps": 10})
        tied_session = self._completed_session({"exercise": self.pushup, "reps": 8})

        self.assertEqual(detect_new_records(self.user, tied_session), [])

    def test_completing_session_shows_new_pr_message(self):
        plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        day = WorkoutPlanDay.objects.create(plan=plan, day_index=0, label="Full Body")
        session = WorkoutSession.objects.create(user=self.user, plan_day=day)
        ExerciseLog.objects.create(session=session, exercise=self.pushup, set_number=1, reps=20)

        response = self.client.post(
            reverse("workouts:session_complete", args=[session.id]), {"notes": ""}, follow=True
        )
        self.assertContains(response, "New PR: Push-up")

    def test_records_page_lists_personal_bests(self):
        self._completed_session({"exercise": self.pushup, "reps": 12})
        response = self.client.get(reverse("workouts:personal_records"))
        self.assertContains(response, "Push-up")
        self.assertContains(response, "12 reps")


class ExerciseLibraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.pullup = make_exercise(
            "Pull-up", "pull", difficulty=ExperienceLevel.INTERMEDIATE, equipment=[Equipment.PULL_UP_BAR]
        )
        self.pushup = make_exercise("Push-up", "push", difficulty=ExperienceLevel.BEGINNER)

    def test_library_lists_all_exercises_with_no_filters(self):
        response = self.client.get(reverse("workouts:exercise_library"))
        self.assertContains(response, "Pull-up")
        self.assertContains(response, "Push-up")

    def test_search_by_name_filters_results(self):
        response = self.client.get(reverse("workouts:exercise_library"), {"q": "pull"})
        self.assertContains(response, "Pull-up")
        self.assertNotContains(response, "Push-up")

    def test_filter_by_category(self):
        response = self.client.get(reverse("workouts:exercise_library"), {"category": "push"})
        self.assertContains(response, "Push-up")
        self.assertNotContains(response, "<h3>Pull-up</h3>")

    def test_filter_by_difficulty(self):
        response = self.client.get(reverse("workouts:exercise_library"), {"difficulty": "beginner"})
        self.assertContains(response, "Push-up")
        self.assertNotContains(response, "<h3>Pull-up</h3>")

    def test_filter_by_equipment(self):
        response = self.client.get(reverse("workouts:exercise_library"), {"equipment": "pull_up_bar"})
        self.assertContains(response, "Pull-up")
        self.assertNotContains(response, "Push-up")

    def test_detail_page_shows_instructions(self):
        response = self.client.get(reverse("workouts:exercise_detail", args=[self.pushup.slug]))
        self.assertContains(response, "Push-up")
        self.assertContains(response, "Do it with good form.")

    def test_detail_page_shows_personal_best_when_set(self):
        session = WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        ExerciseLog.objects.create(session=session, exercise=self.pushup, set_number=1, reps=25)
        response = self.client.get(reverse("workouts:exercise_detail", args=[self.pushup.slug]))
        self.assertContains(response, "25 reps")

    def test_unknown_slug_returns_404(self):
        response = self.client.get(reverse("workouts:exercise_detail", args=["not-a-real-exercise"]))
        self.assertEqual(response.status_code, 404)


class MobilityLibraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.wrist_mobility = Exercise.objects.create(
            name="Wrist Circles", category="mobility", difficulty_level=ExperienceLevel.BEGINNER,
            target_muscles="Wrists, forearms", instructions="Circle gently.",
        )
        self.hip_mobility = Exercise.objects.create(
            name="Hip Switch", category="mobility", difficulty_level=ExperienceLevel.BEGINNER,
            target_muscles="Hips", instructions="Switch sides.",
        )
        # Not a mobility exercise, so it should never appear in any routine.
        make_exercise("Push-up", "push")

    def test_routines_group_by_target_area(self):
        from .mobility import mobility_routines

        routines = {r["key"]: r["exercises"] for r in mobility_routines()}
        self.assertIn(self.wrist_mobility, routines["wrists"])
        self.assertIn(self.hip_mobility, routines["hips"])
        self.assertNotIn(self.hip_mobility, routines.get("wrists", []))

    def test_library_page_lists_routines(self):
        response = self.client.get(reverse("workouts:mobility_library"))
        self.assertContains(response, "Wrist Circles")
        self.assertContains(response, "Hip Switch")
        self.assertNotContains(response, "Push-up")

    def test_routine_for_focus_areas_matches_pull_to_shoulders(self):
        from .mobility import routine_for_focus_areas

        Exercise.objects.create(
            name="Wall Slide", category="mobility", difficulty_level=ExperienceLevel.BEGINNER,
            target_muscles="Shoulders", instructions="Slide up the wall.",
        )
        routine = routine_for_focus_areas(["Pull"])
        self.assertEqual(routine["key"], "shoulders")

    def test_routine_for_focus_areas_returns_none_without_a_match(self):
        from .mobility import routine_for_focus_areas

        Exercise.objects.all().delete()
        self.assertIsNone(routine_for_focus_areas(["Pull"]))


class SkillTreeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        # Names chosen so slugify() matches the l_sit tree's root slug ("plank").
        self.plank = make_exercise("Plank", "core", movement_type="hold", hold=30)
        self.hollow_hold = make_exercise("Hollow Body Hold", "core", movement_type="hold", hold=20)
        self.l_sit = make_exercise("L-sit", "core", movement_type="hold", hold=10)
        self.plank.harder_variation = self.hollow_hold
        self.plank.save()
        self.hollow_hold.harder_variation = self.l_sit
        self.hollow_hold.save()

    def test_chain_follows_harder_variation_links(self):
        from .skill_trees import skill_trees

        tree = next(t for t in skill_trees() if t["key"] == "l_sit")
        self.assertEqual([s["exercise"] for s in tree["steps"]], [self.plank, self.hollow_hold, self.l_sit])

    def test_next_step_is_first_unachieved(self):
        from .skill_trees import skill_trees

        tree = next(t for t in skill_trees({self.plank.id}) if t["key"] == "l_sit")
        self.assertTrue(tree["steps"][0]["achieved"])
        self.assertFalse(tree["steps"][1]["achieved"])
        self.assertEqual(tree["next_step"], self.hollow_hold)

    def test_no_next_step_when_all_achieved(self):
        from .skill_trees import skill_trees

        all_ids = {self.plank.id, self.hollow_hold.id, self.l_sit.id}
        tree = next(t for t in skill_trees(all_ids) if t["key"] == "l_sit")
        self.assertIsNone(tree["next_step"])

    def test_tree_missing_without_a_seeded_root(self):
        from .skill_trees import skill_trees

        self.plank.delete()
        self.assertFalse(any(t["key"] == "l_sit" for t in skill_trees()))

    def test_overview_page_shows_tree(self):
        response = self.client.get(reverse("workouts:skill_tree_overview"))
        self.assertContains(response, "Plank")
        self.assertContains(response, "L-sit")

    def test_toggle_marks_then_unmarks_milestone(self):
        url = reverse("workouts:skill_milestone_toggle", args=[self.plank.id])
        self.client.post(url)
        self.assertTrue(SkillMilestone.objects.filter(user=self.user, exercise=self.plank).exists())

        self.client.post(url)
        self.assertFalse(SkillMilestone.objects.filter(user=self.user, exercise=self.plank).exists())

    def test_cannot_see_another_users_milestones(self):
        other = User.objects.create_user("other3", "o3@example.com", "password123!")
        SkillMilestone.objects.create(user=other, exercise=self.plank)

        response = self.client.get(reverse("workouts:skill_tree_overview"))
        tree = next(t for t in response.context["trees"] if t["key"] == "l_sit")
        self.assertFalse(tree["steps"][0]["achieved"])


class ProgramTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.pushup = make_exercise("Push-up", "push", reps=10)
        self.plank = make_exercise("Plank", "core", movement_type="hold", hold=30)

        self.template = ProgramTemplate.objects.create(
            slug="mixed-training", name="Mixed Training", tagline="All-round athlete",
            skill_rating=5, muscle_rating=4, strength_rating=4, athleticism_rating=5,
        )
        self.training_day = ProgramTemplateDay.objects.create(
            template=self.template, difficulty="easy", day_index=0, label="Push", is_rest_day=False
        )
        ProgramTemplateExercise.objects.create(
            day=self.training_day, exercise=self.pushup, order=0, prescription="3 x 12",
            target_sets=3, target_reps=12, target_hold_seconds=None,
        )
        ProgramTemplateExercise.objects.create(
            day=self.training_day, exercise=self.plank, order=1, prescription="3 x 30 sec",
            target_sets=3, target_reps=None, target_hold_seconds=30,
        )
        self.rest_day = ProgramTemplateDay.objects.create(
            template=self.template, difficulty="easy", day_index=1, label="Rest", is_rest_day=True
        )

    def test_program_list_shows_template(self):
        response = self.client.get(reverse("workouts:program_list"))
        self.assertContains(response, "Mixed Training")

    def test_program_detail_shows_exercises_and_prescriptions(self):
        response = self.client.get(reverse("workouts:program_detail", args=["mixed-training", "easy"]))
        self.assertContains(response, "Push-up")
        self.assertContains(response, "3 x 12")
        self.assertContains(response, "Rest")

    def test_unknown_difficulty_redirects_to_list(self):
        response = self.client.get(reverse("workouts:program_detail", args=["mixed-training", "nonsense"]))
        self.assertRedirects(response, reverse("workouts:program_list"))

    def test_starting_program_creates_active_plan_with_cloned_exercises(self):
        response = self.client.post(reverse("workouts:program_start", args=["mixed-training", "easy"]))
        self.assertRedirects(response, reverse("workouts:plan_overview"))

        plan = WorkoutPlan.objects.get(user=self.user, is_active=True)
        self.assertEqual(plan.source_template, self.template)
        self.assertEqual(plan.source_difficulty, "easy")
        self.assertEqual(plan.training_days_per_week, 1)

        day = plan.days.get(day_index=0)
        self.assertEqual(day.label, "Push")
        exercises = list(day.exercises.order_by("order"))
        self.assertEqual(exercises[0].exercise, self.pushup)
        self.assertEqual(exercises[0].target_reps, 12)
        self.assertEqual(exercises[1].exercise, self.plank)
        self.assertEqual(exercises[1].target_hold_seconds, 30)

        rest = plan.days.get(day_index=1)
        self.assertTrue(rest.is_rest_day)

    def test_starting_program_deactivates_previous_plan(self):
        old_plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        self.client.post(reverse("workouts:program_start", args=["mixed-training", "easy"]))
        old_plan.refresh_from_db()
        self.assertFalse(old_plan.is_active)

    def test_starting_program_requires_post(self):
        response = self.client.get(reverse("workouts:program_start", args=["mixed-training", "easy"]))
        self.assertRedirects(response, reverse("workouts:program_detail", args=["mixed-training", "easy"]))
        self.assertFalse(WorkoutPlan.objects.filter(user=self.user).exists())

    def test_warns_when_equipment_missing_from_profile(self):
        bar_exercise = make_exercise("Pull-up", "pull", reps=8, equipment=[Equipment.PULL_UP_BAR])
        ProgramTemplateExercise.objects.create(
            day=self.training_day, exercise=bar_exercise, order=2, prescription="3 x 8",
            target_sets=3, target_reps=8, target_hold_seconds=None,
        )
        self.user.profile.equipment = []
        self.user.profile.save()

        response = self.client.get(reverse("workouts:program_detail", args=["mixed-training", "easy"]))
        self.assertContains(response, "Pull-up bar")

    def test_no_warning_when_equipment_matches_profile(self):
        bar_exercise = make_exercise("Pull-up", "pull", reps=8, equipment=[Equipment.PULL_UP_BAR])
        ProgramTemplateExercise.objects.create(
            day=self.training_day, exercise=bar_exercise, order=2, prescription="3 x 8",
            target_sets=3, target_reps=8, target_hold_seconds=None,
        )
        self.user.profile.equipment = [Equipment.PULL_UP_BAR]
        self.user.profile.save()

        response = self.client.get(reverse("workouts:program_detail", args=["mixed-training", "easy"]))
        self.assertNotContains(response, "isn't in your profile")

    def test_recommended_template_matches_profile_goal(self):
        self.user.profile.primary_goal = PrimaryGoal.GENERAL_FITNESS
        self.user.profile.save()
        response = self.client.get(reverse("workouts:program_list"))
        self.assertContains(response, "Matches your goal")

    def test_recommended_difficulty_matches_profile_experience(self):
        self.user.profile.experience_level = ExperienceLevel.BEGINNER
        self.user.profile.save()
        response = self.client.get(reverse("workouts:program_detail", args=["mixed-training", "easy"]))
        self.assertContains(response, "Recommended for you")


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

    def test_suggestion_is_none_with_no_data(self):
        note = RecoveryNote.objects.create(user=self.user)
        self.assertFalse(note.has_readiness_data)
        self.assertIsNone(note.suggestion)

    def test_suggestion_flags_poor_sleep(self):
        note = RecoveryNote.objects.create(user=self.user, sleep_quality=1)
        self.assertIn("going easier", note.suggestion)

    def test_suggestion_flags_high_soreness(self):
        note = RecoveryNote.objects.create(user=self.user, soreness=5)
        self.assertIn("going easier", note.suggestion)

    def test_suggestion_flags_high_fatigue(self):
        note = RecoveryNote.objects.create(user=self.user, fatigue=4)
        self.assertIn("going easier", note.suggestion)

    def test_suggestion_is_positive_for_good_numbers(self):
        note = RecoveryNote.objects.create(user=self.user, sleep_quality=5, soreness=1, fatigue=1)
        self.assertIn("Looking good", note.suggestion)

    def test_plan_overview_shows_checkin_prompt_with_no_note_yet(self):
        plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        WorkoutPlanDay.objects.create(plan=plan, day_index=timezone.localdate().weekday(), label="Full Body")
        response = self.client.get(reverse("workouts:plan_overview"))
        self.assertContains(response, "How are you feeling today?")

    def test_plan_overview_shows_readiness_summary_once_logged(self):
        plan = WorkoutPlan.objects.create(
            user=self.user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=3, session_duration_minutes=45, is_active=True,
        )
        WorkoutPlanDay.objects.create(plan=plan, day_index=timezone.localdate().weekday(), label="Full Body")
        RecoveryNote.objects.create(user=self.user, sleep_quality=4, soreness=1, fatigue=1)

        response = self.client.get(reverse("workouts:plan_overview"))
        self.assertContains(response, "Today's readiness")
        self.assertContains(response, "Looking good")
        self.assertNotContains(response, "How are you feeling today?")


def _gemini_days_envelope(raw_days):
    import json

    return {"candidates": [{"content": {"parts": [{"text": json.dumps(raw_days)}]}}]}


def _full_valid_days(push_id, pull_id, legs_id, training_indices=(0, 2, 4)):
    """7 day entries: every training day uses all of push/pull/legs (at
    least MIN_EXERCISES_PER_DAY=3 so each day validates), everything else
    is a rest day. Matches training_days_per_week=3."""
    ids = [push_id, pull_id, legs_id]
    days = []
    for day_index in range(7):
        if day_index in training_indices:
            days.append({
                "day_index": day_index, "label": "Training", "is_rest_day": False,
                "exercises": [{"exercise_id": ex_id, "sets": 3, "reps": 10, "rest_seconds": 60} for ex_id in ids],
            })
        else:
            days.append({"day_index": day_index, "label": "Rest", "is_rest_day": True, "exercises": []})
    return days


class WorkoutAIClientTests(TestCase):
    def setUp(self):
        self.push = make_exercise("Push-up", "push", reps=10)
        self.pull = make_exercise("Table Row", "pull", reps=10)
        self.legs = make_exercise("Squat", "legs", reps=10)
        self.all_exercises = list(Exercise.objects.all())

    def test_raises_configuration_error_without_api_key(self):
        with self.assertRaises(WorkoutAIConfigurationError):
            generate_plan_with_ai(
                self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="",
            )

    @patch("workouts.ai_client._call_gemini")
    def test_valid_response_builds_seven_days_with_warmup_and_cooldown(self, mock_call):
        warmup = make_exercise("Arm Circles", "warmup", reps=20)
        cooldown = make_exercise("Quad Stretch", "cooldown", movement_type="hold", hold=30)
        all_exercises = self.all_exercises + [warmup, cooldown]

        raw_days = _full_valid_days(self.push.id, self.pull.id, self.legs.id)
        mock_call.return_value = _gemini_days_envelope(raw_days)

        days = generate_plan_with_ai(
            all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="test-key",
        )
        self.assertEqual(len(days), 7)
        training_days = [d for d in days if not d.is_rest_day]
        self.assertEqual(len(training_days), 3)
        for day in training_days:
            names = [pe.exercise.name for pe in day.exercises]
            self.assertIn("Arm Circles", names)
            self.assertIn("Quad Stretch", names)

    @patch("workouts.ai_client._call_gemini")
    def test_wrong_training_day_count_raises_and_does_not_silently_change_it(self, mock_call):
        # Only 2 of the 7 days are training, but the caller asked for 3 -
        # the response must be rejected rather than silently using 2.
        raw_days = _full_valid_days(self.push.id, self.pull.id, self.legs.id, training_indices=(0, 2))
        mock_call.return_value = _gemini_days_envelope(raw_days)

        with self.assertRaises(WorkoutAIResponseError):
            generate_plan_with_ai(
                self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="test-key",
            )

    @patch("workouts.ai_client._call_gemini")
    def test_unknown_exercise_id_is_dropped_not_trusted(self, mock_call):
        raw_days = _full_valid_days(self.push.id, self.pull.id, self.legs.id)
        # Sneak in a bogus id alongside a valid one on day 0.
        raw_days[0]["exercises"].append({"exercise_id": 999999, "sets": 3, "reps": 10, "rest_seconds": 60})
        mock_call.return_value = _gemini_days_envelope(raw_days)

        days = generate_plan_with_ai(
            self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="test-key",
        )
        day0 = next(d for d in days if d.day_index == 0)
        ids_used = {pe.exercise.id for pe in day0.exercises}
        self.assertNotIn(999999, ids_used)

    @patch("workouts.ai_client._call_gemini")
    def test_out_of_range_prescription_values_are_clamped(self, mock_call):
        raw_days = _full_valid_days(self.push.id, self.pull.id, self.legs.id)
        raw_days[0]["exercises"][0] = {"exercise_id": self.push.id, "sets": 999, "reps": 999, "rest_seconds": 999999}
        mock_call.return_value = _gemini_days_envelope(raw_days)

        days = generate_plan_with_ai(
            self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="test-key",
        )
        day0 = next(d for d in days if d.day_index == 0)
        main = [pe for pe in day0.exercises if pe.exercise.id == self.push.id][0]
        self.assertLessEqual(main.target_sets, 6)
        self.assertLessEqual(main.target_reps, 50)
        self.assertLessEqual(main.rest_seconds, 240)

    @patch("workouts.ai_client._call_gemini")
    def test_malformed_json_raises_response_error(self, mock_call):
        mock_call.return_value = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
        with self.assertRaises(WorkoutAIResponseError):
            generate_plan_with_ai(
                self.all_exercises, ExperienceLevel.BEGINNER, [], PrimaryGoal.GENERAL_FITNESS, 3, 45, api_key="test-key",
            )


class WorkoutAIRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")

    def test_remaining_decreases_with_use(self):
        self.assertEqual(requests_remaining_today(self.user), 10)
        record_attempt_or_raise(self.user)
        self.assertEqual(requests_remaining_today(self.user), 9)

    @override_settings(WORKOUT_AI_DAILY_LIMIT=2)
    def test_raises_once_daily_limit_is_reached(self):
        record_attempt_or_raise(self.user)
        record_attempt_or_raise(self.user)
        with self.assertRaises(RateLimitExceeded):
            record_attempt_or_raise(self.user)
        self.assertEqual(WorkoutPlanAIRequest.objects.filter(user=self.user).count(), 2)


@override_settings(GEMINI_API_KEY="test-key")
class PlanGenerateAIIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.push = make_exercise("Push-up", "push", reps=10)
        self.pull = make_exercise("Table Row", "pull", reps=10)
        self.legs = make_exercise("Squat", "legs", reps=10)
        make_exercise("Warmup A", "warmup", reps=20)
        make_exercise("Cooldown A", "cooldown", movement_type="hold", hold=30)

    @patch("workouts.views.generate_plan_with_ai")
    def test_uses_ai_plan_when_available(self, mock_generate):
        from .generation import PlannedDay, PlannedExercise

        mock_generate.return_value = [
            PlannedDay(day_index=i, label="Rest", is_rest_day=True) for i in range(7)
        ]
        mock_generate.return_value[0] = PlannedDay(
            day_index=0, label="AI Day", is_rest_day=False,
            exercises=[PlannedExercise(exercise=self.push, target_sets=3, target_reps=10, target_hold_seconds=None, rest_seconds=60)],
        )
        response = self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 1, "session_duration_minutes": 45, "equipment": [],
        }, follow=True)
        self.assertContains(response, "AI-personalized")
        plan = WorkoutPlan.objects.get(user=self.user)
        self.assertEqual(plan.days.get(day_index=0).label, "AI Day")

    @patch("workouts.views.generate_plan_with_ai", side_effect=WorkoutAIConfigurationError("not configured"))
    def test_falls_back_to_deterministic_generator_on_ai_failure(self, mock_generate):
        response = self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45, "equipment": [],
        }, follow=True)
        self.assertNotContains(response, "AI-personalized")
        self.assertContains(response, "Your workout plan is ready")
        self.assertTrue(WorkoutPlan.objects.filter(user=self.user).exists())

    @patch("workouts.views.workout_ai_record_attempt_or_raise", side_effect=RateLimitExceeded(retry_after=None))
    def test_falls_back_with_message_when_rate_limited(self, mock_record):
        response = self.client.post(reverse("workouts:plan_generate"), {
            "goal": "general_fitness", "experience_level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45, "equipment": [],
        }, follow=True)
        self.assertContains(response, "today&#x27;s limit")
        self.assertTrue(WorkoutPlan.objects.filter(user=self.user).exists())
