# Peakform

A fitness and nutrition platform combining personalized nutrition tracking,
AI-powered food logging, calisthenics workout planning, guided workouts,
daily activity tracking, progress tracking, and a global fitness community.

See [docs/Peakform.md](docs/Peakform.md) for the full product brief.

## Status

**Phase 7 — Global community.** Django project scaffolded with
environment-driven configuration, a responsive base template and design
system, the landing page, authentication/onboarding/profiles, nutrition
calculations with a food diary and water/step trackers and Gemini-powered
natural-language food logging, a calisthenics workout planner with
guided sessions and progressive overload, streaks/weekly goals/badges,
and now a public community feed: text posts (with an optional photo)
about meals, recipes, workout programs, training photos, skills, and
progress; likes; one level of threaded comments/replies; following other
users and a dedicated following feed; public profiles; editing and
deleting your own content; and reporting posts or comments for spam,
harassment, misleading content, or inappropriate images. Anyone can
browse the feed and public profiles; posting, commenting, liking,
following, and reporting require signing in. Authorization is enforced
server-side (editing/deleting another user's content 404s rather than
succeeding), uploaded images are restricted by file extension and a 5MB
size cap, and moderators can hide reported content from the Django admin
without deleting the underlying record. Polish and deployment land in
the final phase per the brief's roadmap.

**Known content gap:** exercise demonstration videos are not yet
populated (`Exercise.video_url` is left blank for all seeded exercises)
rather than filled with guessed YouTube links — the UI supports an
embedded video per exercise once real, verified URLs are curated.

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
accounts/       User profiles and onboarding
nutrition/      Nutrition calculations, food diary, AI food logging
workouts/       Calisthenics workout planning and guided sessions
motivation/     Streaks, weekly goals, and badges
community/      Public feed, posts, comments, follows, reports
templates/      Shared base template
static/         Design system CSS and JS
docs/           Product brief
```
