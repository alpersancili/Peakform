# Peakform

A fitness and nutrition platform combining personalized nutrition tracking,
AI-powered food logging, calisthenics workout planning, guided workouts,
daily activity tracking, progress tracking, and a global fitness community.

See [docs/Peakform.md](docs/Peakform.md) for the full product brief.

## Status

**MVP complete (Phases 1–8).** Django project with environment-driven
configuration, a responsive, accessible base template and design system
(light/dark, keyboard-navigable, skip link), the landing page,
authentication/onboarding/profiles, nutrition calculations (BMI/BMR/
TDEE/macros) with a food diary and water/step trackers, Gemini-powered
natural-language food logging with validated, editable estimates, a
calisthenics workout planner with guided sessions and progressive
overload, streaks/weekly goals/badges, a public community feed (posts,
images, likes, threaded comments, following, profiles, reporting and
admin moderation), and production deployment configuration (gunicorn,
WhiteNoise static files, HTTPS/HSTS/secure-cookie hardening, console
logging). 139 automated tests cover the deterministic calculation logic,
generation algorithms, and server-side permission checks across every
app.

**Known content gap:** exercise demonstration videos are not yet
populated (`Exercise.video_url` is left blank for all seeded exercises)
rather than filled with guessed YouTube links — the UI supports an
embedded video per exercise once real, verified URLs are curated.

**Deferred to a future release** (per the brief's section 5 — not MVP
scope): AI food photo recognition, calisthenics skill roadmaps, an
advanced AI coach with weekly summaries, automated recovery analysis
from logged sleep/soreness trends, and expanded gamification (weekly
and community challenges). The architecture doesn't block adding these
later — e.g. `RecoveryNote` already exists for the manual version that
automated recovery analysis would build on.

Seed reference data after migrating:

```bash
python manage.py seed_foods
python manage.py seed_exercises
python manage.py seed_badges
```

## Tech stack

- **Backend:** Python 3 + Django
- **Database:** PostgreSQL (Supabase in production), SQLite for local dev
- **AI:** Google Gemini API (natural-language food logging)
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
| `GEMINI_API_KEY` | Google Gemini API key for the AI nutrition assistant. Unset = the feature is disabled with a clear in-app message; nothing else breaks. |
| `GEMINI_MODEL` | Gemini model id (default `gemini-3.1-flash-lite`). |
| `GEMINI_DAILY_LIMIT` | Max AI food-logging requests per user per day (default `20`), to bound cost and abuse. |
| `SUPABASE_S3_ACCESS_KEY_ID` / `SUPABASE_S3_SECRET_ACCESS_KEY` | Supabase Storage S3 credentials, from Project Settings -> Storage -> S3 Connection. Unset = uploads go to local disk. |
| `SUPABASE_S3_ENDPOINT_URL` | e.g. `https://<ref>.storage.supabase.co/storage/v1/s3`, from the same S3 Connection page. |
| `SUPABASE_S3_REGION` | Your Supabase project's region, e.g. `eu-central-1`. |
| `SUPABASE_S3_BUCKET` | Storage bucket name (default `community-images`). |

## Running tests

```bash
python manage.py test
```

139 tests cover the deterministic nutrition/workout-generation/streak
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
   migrations and starts gunicorn: `python manage.py migrate --noinput
   && gunicorn peakform.wsgi --log-file -`. Railway and Render both read
   a `Procfile` automatically; for Render specifically, set the build
   command to `pip install -r requirements.txt && python manage.py
   collectstatic --noinput` and the start command to `gunicorn
   peakform.wsgi --log-file -` (Render runs migrations as a separate
   step rather than via the Procfile).
6. **Media storage:** local disk (`MEDIA_ROOT`) by default, which isn't
   persistent across redeploys on most platform-as-a-service hosts. Set
   the `SUPABASE_S3_*` variables (see above) to store uploads in
   Supabase Storage instead, over its S3-compatible API — reads go
   straight to Supabase's public object URL (the bucket is public and
   read-only for anonymous requests; all writes require the S3
   credentials, which only the server holds).
7. Seed reference data once, after the first deploy:
   `python manage.py seed_foods && python manage.py seed_exercises &&
   python manage.py seed_badges` (idempotent — safe to re-run).

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
templates/      Shared base template
static/         Design system CSS and JS
docs/           Product brief
```
