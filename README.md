# Peakform

A fitness and nutrition platform combining personalized nutrition tracking,
AI-powered food logging, calisthenics workout planning, guided workouts,
daily activity tracking, progress tracking, and a global fitness community.

See [docs/Peakform.md](docs/Peakform.md) for the full product brief.

## Status

**MVP complete (Phases 1–8), plus a full round of post-MVP features.**
Django project with environment-driven configuration, a responsive,
accessible base template and design system (light/dark,
keyboard-navigable, skip link), the landing page,
authentication/onboarding/profiles, nutrition calculations (BMI/BMR/
TDEE/macros) with a food diary and water/step trackers, a calisthenics
workout planner with guided sessions and progressive overload,
streaks/weekly goals/badges, a public community feed (posts, images,
likes, threaded comments, following, profiles, reporting and admin
moderation), progress tracking (weight and optional body measurement
history, a weight trend, calorie-target consistency over the last 7
days, and water/step trends, alongside workout history and streaks),
Supabase Storage for durable image uploads, and production deployment
configuration (gunicorn, WhiteNoise static files, HTTPS/HSTS/
secure-cookie hardening, console logging), and a conversational AI
coach grounded in the user's real logged data (profile, nutrition
targets vs. today's intake, active workout plan and history, streak,
weight trend) rather than invented numbers - it asks for missing
information instead of guessing, avoids diagnosing medical conditions,
and never promises specific results or timelines. 305 automated tests
cover the deterministic calculation logic, generation algorithms, and
server-side permission checks across every app.

**AI-assisted nutrition and training:** Gemini-powered natural-language
food logging and a meal-photo scanner (both with validated, editable
estimates before anything is logged), and an AI-assisted workout plan
generator that designs a full 7-day training cycle from the user's
goal/experience/equipment/availability - constrained to only reference
exercises that already pass equipment and experience filtering, with
every id and prescription value server-validated, and falling back to
a deterministic rule-based generator whenever the AI is unconfigured,
rate-limited, or returns anything invalid.

**Progress, records, and motivation:** a progress-photo gallery with
before/after comparison, automatic personal-record detection (best
reps or hold per exercise) with in-session "New PR" callouts, a
searchable/filterable exercise library, and an XP/leveling system with
weekly challenges layered on top of the MVP's badges and streaks.

**Structured programs:** three hand-curated, named training programs
(Skill-focused, Strength & Hypertrophy, Mixed Training), each at
Easy/Intermediate/Difficult tiers, browsable day-by-day and
one-click-startable into a fully tracked plan.

**Exercise library:** 91 exercises (including full dips, hanging leg
raises, complete planche/front lever/one-arm-handstand progressions,
dedicated conditioning and mobility pools, and more), each with a real
YouTube demonstration URL where one could be confidently sourced
(individually verified, never guessed/fabricated) or detailed written
instructions where one couldn't — every mobility/flexibility exercise
now has one. Workout generation scales sets/reps/
rest to the user's actual goal and varies the weekly split structure
itself by goal (Skills gets dedicated Push/Pull days; Endurance and
Flexibility get genuine Conditioning/Mobility sessions, not a
relabeled strength split), spreads training days across the week
instead of clustering them, and sequences skill work first in a
session while fresh.

**The workout experience:** a focused, one-exercise-at-a-time active
workout mode with a progress bar and auto-resume past completed
exercises; set logging pre-filled from the matching set in your last
session of that exercise; a per-day overview showing difficulty,
equipment, muscle groups, and working-set count before you start; a
workout completion summary with PR callouts, a volume comparison
against your last session, and a recommended cooldown routine; the
ability to swap out an exercise mid-session (with a safety note if the
reason is discomfort); named skill progression trees (handstand,
muscle-up, planche, front lever, pistol squat, L-sit, and more) built
from the exercise library's own progression chains, with a way to mark
a step achieved, plus user-defined custom skill goals (a free-text
target broken into the user's own steps, for anything not in the
curated trees); a mobility & recovery library grouped into routines
by target area; a pre-session readiness check-in (sleep/soreness/
fatigue) with a plain-language, non-diagnostic suggestion; a
training-volume trend chart with 8/12/26-week filters; and
user-published community routines that others can browse, start, rate,
and report, moderated through the same system as community posts.

**Not yet built:** self-service password reset (removed after
shipping it, since the email provider's free tier can't deliver to
real users without a verified domain), a drag-to-reorder weekly
calendar, multi-day trend analysis of logged recovery data (today's
check-in gives a same-day suggestion, not a trend over time), training
partner matching, and wearable/device integrations.

Seed reference data after migrating:

```bash
python manage.py seed_foods
python manage.py seed_exercises
python manage.py seed_programs
python manage.py seed_badges
python manage.py seed_challenges
```

## Tech stack

- **Backend:** Python 3 + Django
- **Database:** PostgreSQL (Supabase in production), SQLite for local dev
- **AI:** Google Gemini API (natural-language and photo food logging, conversational coach, AI-assisted workout plan generation)
- **Frontend:** Django templates, vanilla CSS/JS (no frontend framework)
- **Static files:** WhiteNoise
- **Deployment:** Railway/Render-style Django hosting (not Vercel — see
  "Deployment" below)

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # defaults work out of the box with local SQLite

python manage.py migrate
python manage.py runserver
```

Visit http://localhost:8000.

## Environment variables

See [.env.example](.env.example) for the full list. Nothing is required for
local development — the app falls back to SQLite and runs with Gemini
integration disabled until `GEMINI_API_KEY` is set and `DATABASE_URL` is
left unset.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django's cryptographic signing key. Required in production — generate a long random value, e.g. `python -c "import secrets; print(secrets.token_urlsafe(50))"`. |
| `DJANGO_DEBUG` | `True` locally, `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames Django will serve. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (with scheme) allowed to submit forms, e.g. your production domain. |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` in production to redirect HTTP to HTTPS (default `True`; the host's load balancer must forward `X-Forwarded-Proto`). |
| `DJANGO_LOG_LEVEL` | Console log level in production (`INFO` by default; `DEBUG` for more verbose troubleshooting). |
| `DATABASE_URL` | Postgres connection string (Supabase). Unset = local SQLite. |
| `GEMINI_API_KEY` | Google Gemini API key, shared by the AI nutrition assistant, the AI coach, and AI-assisted workout plan generation. Unset = each feature is disabled with a clear in-app message (or a deterministic fallback, for workout plans); nothing else breaks. |
| `GEMINI_MODEL` | Gemini model id (default `gemini-3.1-flash-lite`). |
| `GEMINI_DAILY_LIMIT` | Max AI food-logging requests per user per day (default `20`), to bound cost and abuse. |
| `COACH_DAILY_LIMIT` | Max AI coach messages per user per day (default `30`). |
| `WORKOUT_AI_DAILY_LIMIT` | Max AI-personalized workout plan generations per user per day (default `10`). Uses the same `GEMINI_API_KEY`; when unset or over the limit, plan generation silently falls back to the deterministic rule-based generator. |
| `SUPABASE_S3_ACCESS_KEY_ID` / `SUPABASE_S3_SECRET_ACCESS_KEY` | Supabase Storage S3 credentials, from Project Settings -> Storage -> S3 Connection. Unset = uploads go to local disk. |
| `SUPABASE_S3_ENDPOINT_URL` | e.g. `https://<ref>.storage.supabase.co/storage/v1/s3`, from the same S3 Connection page. |
| `SUPABASE_S3_REGION` | Your Supabase project's region, e.g. `eu-central-1`. |
| `SUPABASE_S3_BUCKET` | Storage bucket name (default `community-images`). |

## Running tests

```bash
python manage.py test
```

305 tests cover the deterministic nutrition/workout-generation/streak
calculations (no AI involved — these are pure functions with their own
unit tests), form validation, and — for every view that lets a user
modify data — that another user genuinely cannot (edit/delete/moderate
endpoints return 404 rather than succeeding for a non-owner). The
Gemini API is never called in tests; `nutrition/ai_client.py`'s HTTP
call is mocked.

## Deployment

Django does not fit Vercel's serverless model well (no persistent
processes, and static/media handling requires extra configuration). This
project targets a standard Django host instead — **Railway** or
**Render** both work well (a long-running WSGI process, managed Postgres
if you don't use Supabase directly, and simple environment variable
management).

1. **Database:** create a Supabase Postgres project (or use the host's
   managed Postgres) and copy its connection string into `DATABASE_URL`.
2. **Set environment variables** on the host: at minimum
   `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`
   (your domain), `DJANGO_CSRF_TRUSTED_ORIGINS` (`https://yourdomain...`),
   and `DATABASE_URL`. Add `GEMINI_API_KEY` to enable the AI assistant.
3. **Build:** `pip install -r requirements.txt`.
4. **Static files:** run `python manage.py collectstatic --noinput`
   during the build step (WhiteNoise then serves hashed, cached assets
   directly from the Django process — no separate static host needed).
5. **Release/start command:** the included [`Procfile`](Procfile) runs
   migrations, seeds reference data, and starts gunicorn: `python
   manage.py migrate --noinput && python manage.py seed_foods && python
   manage.py seed_exercises && python manage.py seed_programs && python
   manage.py seed_badges && python manage.py seed_challenges && gunicorn
   peakform.wsgi --log-file -`. Running the seed commands on every boot
   (not just the first deploy) matters on hosts without shell/SSH access
   (e.g. Render's free tier) - there'd otherwise be no way to run them
   after the first deploy; they're all idempotent, so re-running them is
   a no-op once the data is already there. Railway and Render both read
   a `Procfile` automatically; for Render specifically, set the build
   command to `pip install -r requirements.txt && python manage.py
   collectstatic --noinput` and the start command to the same migrate +
   seed + gunicorn chain above (Render can run this as its start command
   directly, or as a separate "release" step if your plan supports one).
6. **Media storage:** local disk (`MEDIA_ROOT`) by default, which isn't
   persistent across redeploys on most platform-as-a-service hosts. Set
   the `SUPABASE_S3_*` variables (see above) to store uploads in
   Supabase Storage instead, over its S3-compatible API — reads go
   straight to Supabase's public object URL (the bucket is public and
   read-only for anonymous requests; all writes require the S3
   credentials, which only the server holds).
7. Reference data seeds itself on every boot via the Procfile (step 5)
   - no manual step needed, including on hosts with no shell access.
   If you're not using the Procfile for some reason, run the same seed
   commands manually at least once: `python manage.py seed_foods &&
   python manage.py seed_exercises && python manage.py seed_programs &&
   python manage.py seed_badges && python manage.py seed_challenges`
   (`seed_programs` must run after `seed_exercises`, since its curated
   programs reference exercises by name).

Run `python manage.py check --deploy` with your production environment
variables set before going live; it flags missing production hardening
(e.g. a weak `SECRET_KEY`).

## Project structure

```
peakform/       Project settings, root URLs, WSGI/ASGI entry points
core/           Landing page and shared/foundational views
accounts/       User profiles and onboarding
nutrition/      Nutrition calculations, food diary, AI food logging
workouts/       Calisthenics workout planning and guided sessions
motivation/     Streaks, weekly goals, and badges
community/      Public feed, posts, comments, follows, reports
progress/      Weight/measurement history, consistency, trends
coach/         Conversational AI coach, grounded in real user data
templates/      Shared base template
static/         Design system CSS and JS
docs/           Product brief
```

## License

MIT — see [LICENSE](LICENSE).
