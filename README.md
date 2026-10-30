# Peakform

A fitness and nutrition platform combining personalized nutrition tracking,
AI-powered food logging, calisthenics workout planning, guided workouts,
daily activity tracking, progress tracking, and a global fitness community.

See [docs/Peakform.md](docs/Peakform.md) for the full product brief.

## Status

**Phase 3 — Nutrition core and daily dashboard.** Django project scaffolded
with environment-driven configuration, a responsive base template and design
system, the landing page, authentication/onboarding/profiles, and now BMI,
BMR, TDEE, and macro calculations with a food diary, water/step trackers,
and a daily dashboard with a weekly calories chart. Workouts, habits,
AI assistance, and community features land in later phases per the
brief's roadmap.

Seed the shared food catalog after migrating:

```bash
python manage.py seed_foods
```

## Tech stack

- **Backend:** Python 3 + Django
- **Database:** PostgreSQL (Supabase in production), SQLite for local dev
- **AI:** Google Gemini API (Phase 6)
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
| `DJANGO_SECRET_KEY` | Django's cryptographic signing key. Required in production. |
| `DJANGO_DEBUG` | `True` locally, `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames Django will serve. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (with scheme) allowed to submit forms, e.g. your production domain. |
| `DATABASE_URL` | Postgres connection string (Supabase). Unset = local SQLite. |
| `GEMINI_API_KEY` | Google Gemini API key for the AI nutrition assistant. |

## Running tests

```bash
python manage.py test
```

## Deployment

Django does not fit Vercel's serverless model well (no persistent
processes, and static/media handling requires extra configuration). This
project targets a standard Django host instead (e.g. Railway or Render),
which supports a long-running WSGI process, straightforward Postgres
provisioning, and simple environment variable management. Deployment
configuration is finalized in Phase 8 of the roadmap.

## Project structure

```
peakform/       Project settings, root URLs, WSGI/ASGI entry points
core/           Landing page and shared/foundational views
accounts/       User profiles and onboarding (Phase 2)
templates/      Shared base template
static/         Design system CSS and JS
docs/           Product brief
```
