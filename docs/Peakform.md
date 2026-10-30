# PROJECT_BRIEF.md

# Fitness & Nutrition Platform --- Project Brief

## 1. Project Overview

Build a modern, responsive fitness and nutrition website that helps
people improve their health, strength, athletic performance, and overall
well-being.

The platform should combine personalized nutrition tracking, AI-powered
food logging, calisthenics workout planning, guided workouts, daily
activity and hydration tracking, progress tracking, and a global social
community.

The website must provide practical guidance before, during, and after
each workout. It should function as a personalized fitness companion
rather than only generating exercise lists.

The target audience includes everyone from complete beginners to
advanced athletes.

The goal is to launch a polished, functional MVP first, then expand it
based on user feedback.

**Important: Build a website only.** Do not develop native iOS or
Android apps, React Native, or Expo. The website must work well on
desktop, tablet, and mobile browsers.

## 2. Product Vision

Create a platform where users can:

-   Calculate their daily calorie and macronutrient needs.
-   Record meals and track calories, protein, carbohydrates, and fats.
-   Track water intake and daily steps against personalized goals.
-   Receive personalized nutrition recommendations.
-   Generate calisthenics workout plans based on their goals and
    abilities.
-   Follow guided workouts with warm-ups, instructions, rest timers, and
    performance logging.
-   Track body measurements, nutrition, workouts, recovery, and
    progress.
-   Build consistent habits through streaks, weekly goals, and
    milestones.
-   Share meals, recipes, training programs, photos, achievements, and
    thoughts with a global fitness community.
-   Interact with other users through profiles, likes, comments, and
    discussions.
-   Use an AI assistant for practical fitness and nutrition guidance.

The brand should combine **athletic performance and everyday wellness**.
It should feel motivating, credible, modern, and welcoming rather than
intimidating.

## 3. Technology Stack

Use the following technologies where compatible with the existing
repository:

-   **Backend:** Python and Django.
-   **Database:** Supabase PostgreSQL.
-   **AI:** Google Gemini API.
-   **Frontend:** HTML, CSS, JavaScript, and Django templates.
-   **Deployment:** Vercel where compatible with the Django application
    and its requirements; otherwise recommend a compatible Django
    hosting solution and explain why.
-   **Version control:** Git and GitHub.

Use Django for backend logic, authentication, permissions, database
access, and server-rendered pages.

Use JavaScript for interactive frontend components where needed, such
as rest timers, water and step trackers, and charts. Avoid adding a
large frontend framework unless there is a clear technical reason.

Use environment variables for all secrets and API keys. Never expose the
Gemini API key or database credentials in frontend code.

Before choosing or changing dependencies, inspect the existing
repository and explain important compatibility considerations.

## 4. Core Website Features

### 4.1 Landing Page

Create a polished homepage that communicates the platform's value
immediately.

Include:

-   A strong headline and clear call to action.
-   An overview of nutrition tracking, workout planning, guided
    workouts, daily activity tracking, AI assistance, and community
    features.
-   Attractive fitness-related visuals and clean information cards.
-   Example dashboard or progress previews.
-   Links to sign up, sign in, explore the community, and learn about
    the platform.
-   Responsive navigation and footer.

The design should feel like a premium fitness product, not a generic
template.

### 4.2 User Accounts and Onboarding

Users should be able to register, sign in, sign out, and manage their
profiles.

Collect relevant information during onboarding:

-   Age, height, and weight.
-   Sex, when required by the chosen calculation formula.
-   Activity level.
-   Fitness experience: beginner, intermediate, or advanced.
-   Primary goal: fat loss, muscle gain, strength, endurance, skills,
    flexibility, or general fitness.
-   Available training days and time per session.
-   Available equipment.
-   Dietary preferences and restrictions.
-   Country or region and preferred units.

Allow users to edit their information later.

Do not require users to share unnecessary sensitive information. Explain
why personal data is collected and protect it appropriately.

### 4.3 Nutrition Calculator and Daily Dashboard

Calculate and display:

-   BMI (Body Mass Index).
-   BMR (Basal Metabolic Rate).
-   TDEE (Total Daily Energy Expenditure).
-   Daily calorie targets.
-   Daily protein, carbohydrate, and fat targets.

Use established formulas and transparent assumptions. Allow users to
adjust targets where appropriate.

Distinguish estimates from exact measurements. Do not present BMI as a
complete measure of health or athletic performance.

Provide a daily nutrition and activity dashboard containing:

-   Calorie and macronutrient targets based on user information and
    goals, with daily intake versus target.
-   Macronutrient progress.
-   A food diary with recent meals and editable portions, calories,
    protein, carbohydrates, and fats.
-   A water tracker with configurable serving sizes and progress toward
    a personalized hydration goal (see 4.9).
-   A daily step tracker with a customizable target and manual entry in
    the MVP (see 4.9).
-   Workout completion and activity history.
-   Weight and measurement history.
-   Optional meal timing suggestions and practical pre-workout and
    post-workout meal ideas.
-   Daily and weekly summaries that help users understand consistency
    and trends.
-   Progress over time using clear charts.

### 4.4 Food Diary and Meal Logging

Users should be able to log breakfast, lunch, dinner, and snacks.

Each food entry should support:

-   Food name.
-   Portion size and unit.
-   Calories.
-   Protein, carbohydrates, and fats.
-   Meal category.
-   Date and time.

Allow users to search a food database, choose a serving size, change the
quantity, and edit or delete entries.

Calculate nutrition totals from structured food data whenever possible.
AI-generated estimates must be identified as estimates and editable by
the user.

### 4.5 Gemini AI Nutrition Assistant

Integrate the Google Gemini API through the Django backend.

Users should be able to describe a meal in natural language, for
example:

"I ate two eggs, two slices of bread, and a banana."

The assistant should identify likely food items, estimate portions when
necessary, and return structured nutrition information that can be
reviewed before saving.

The assistant may also:

-   Suggest meals that fit the user's remaining calorie and macro
    targets.
-   Suggest practical pre-workout and post-workout meals.
-   Explain nutrition concepts in accessible language.
-   Suggest alternatives based on dietary preferences.
-   Summarize eating patterns.
-   Help users make practical, sustainable improvements.

AI responses must not be treated as verified nutritional facts. Clearly
label AI-produced estimates, validate structured outputs, allow user
corrections, and handle API failures gracefully. Never present
AI-generated nutrition or training suggestions as guaranteed medical
advice.

Do not use blood type to determine diets. Use evidence-informed
nutrition principles, personal preferences, dietary restrictions, and
user goals instead.

### 4.6 Personalized Calisthenics Workout Planner

Generate workout plans based on:

-   User's goal.
-   Fitness experience and current abilities.
-   Available equipment.
-   Days available per week.
-   Time available per session.
-   Recovery needs and exercise preferences.

Support goals such as:

-   Fat loss.
-   Muscle gain.
-   Strength.
-   General fitness.
-   Mobility and flexibility.
-   Calisthenics skills, including pull-ups, dips, muscle-ups,
    handstands, planche progressions, and front lever progressions.

Plans must include planned rest days and help users monitor training
frequency.

Provide beginner-friendly options and gradual progression. Do not
prescribe advanced skills to beginners without the necessary
foundations.

AI can assist with personalization, but workout structure, safety
checks, and progression rules should be implemented with explicit
application logic wherever possible.

### 4.7 Workout Preparation and Guided Sessions

Every workout must display:

-   Estimated workout duration, target muscles, difficulty, and required
    equipment.
-   A warm-up routine with exercise demonstrations and suggested
    durations.
-   For each exercise: sets, repetitions or hold duration, rest between
    sets, technique instructions, breathing guidance, common mistakes,
    and an exercise demonstration video.
-   Easier and harder variations appropriate to the user's level and
    available equipment.
-   Suggested effort using RPE (rate of perceived exertion) or
    repetitions in reserve (RIR) where appropriate.
-   A rest countdown timer, exercise completion controls, and the
    ability to record actual performance (sets, reps, holds, and
    effort).
-   Optional cool-down and mobility suggestions.

Rest recommendations must depend on the exercise and training
objective. Starting defaults may include:

-   30--60 seconds for easy technique work.
-   60--120 seconds for standard bodyweight exercises.
-   90--180 seconds for difficult strength exercises.
-   2--5 minutes for demanding or near-maximal efforts.

These are adjustable guidelines, not rigid rules. Users should be able
to rest longer when needed.

The plan should encourage controlled technique and appropriate
progression. It must not encourage users to continue through sharp
pain, ignore warning symptoms, or train to failure on every set.

Users should be able to mark exercises and workouts as completed and
review their training history.

### 4.8 Recovery and Progressive Training

Allow optional notes for sleep, soreness, fatigue, and perceived
recovery. These notes should inform recommendations but must not be
treated as medical diagnoses.

Use progressive overload principles to recommend gradual changes to
repetitions, hold duration, sets, or exercise difficulty when the
user's logged performance indicates readiness. Do not increase
difficulty automatically without considering performance, technique,
recovery, and user feedback.

### 4.9 Hydration and Daily Activity

-   Water tracker with configurable serving sizes and a personalized
    hydration goal.
-   Daily step tracker with a customizable target and manual entry in
    the MVP.

Hydration and step goals must be presented as personalized estimates,
not universal medical requirements. Hydration guidance should account
for activity and hot weather where practical, and users with medical
fluid restrictions should be advised to follow their clinician's
guidance. Step targets should be adjustable and suitable for the user's
current activity level.

### 4.10 Motivation and Habit Tracking

Connect the profile dashboard with workout history, body-weight history,
exercise performance, daily activity, and streaks.

-   Reward meaningful completed actions with milestones and badges.
-   Support weekly goals and planned rest days (rest days should not
    break streaks).
-   Encourage users to resume after missed goals without shame or
    pressure to overtrain.

Basic streaks and milestones are part of the MVP. Larger challenges and
community competitions are future features (see Section 5).

### 4.11 Progress Tracking

Let users record and review:

-   Body weight.
-   Optional body measurements.
-   Workout history and logged exercise performance.
-   Personal records and skill milestones.
-   Calorie and macro consistency.
-   Water and step history.
-   Weekly and monthly progress.

Store user-entered measurements and workout logs with dates and
preserve historical records.

Use clear charts and summaries.

AI-generated progress summaries may explain patterns and suggest
reasonable next steps. They must avoid unsupported claims, diagnoses, or
promises of specific results.

Progress tracking should encourage consistency rather than shame users
for missed workouts or dietary targets.

### 4.12 Global Fitness Community

Build a public community feed where registered users can share content
with other users around the world.

Users should be able to create posts about:

-   Meals and recipes.
-   Nutrition tips.
-   Workout programs.
-   Training photos.
-   Calisthenics skills and achievements.
-   Personal progress.
-   Fitness experiences, questions, and thoughts.

Community functionality should include:

-   Text posts and image uploads.
-   User profiles.
-   Likes or reactions.
-   Comments and replies where practical.
-   Following other users.
-   Viewing posts from the community.
-   Viewing posts from followed users.
-   Basic post editing and deletion.
-   Reporting inappropriate content.
-   Pagination or incremental loading.

Allow visitors to browse appropriate public content. Require
authentication for actions such as posting, commenting, liking, and
following.

Implement server-side authorization so users cannot edit or delete other
people's content without permission.

Validate uploads, restrict file types and sizes, and use an appropriate
storage solution for images. Do not store large user-uploaded images
directly in database records.

### 4.13 Community Questions and Discussions

Support questions and discussions about fitness, nutrition,
calisthenics, recovery, and training techniques.

Users should be able to ask questions and participate in discussions
through comments or replies.

Keep the initial implementation simple. A full forum system is not
required for the MVP.

Include reporting and basic moderation mechanisms to help handle spam,
harassment, misleading content, and inappropriate images.

## 5. Features for Future Releases

Do not let these features delay the core MVP. Design the architecture so
they can be added later.

### AI Food Photo Recognition

Allow users to upload meal photos and receive estimated food
identification, portion sizes, and nutritional information. Require
confirmation before adding estimates to the food diary.

### Calisthenics Skill Roadmaps

Create structured progression paths for skills such as handstands,
muscle-ups, planche, and front lever, with prerequisites and milestone
tracking.

### Advanced AI Fitness Coach

Offer personalized weekly summaries, habit insights, workout
adjustments, and nutrition suggestions based on recorded progress.

### Automated Recovery Analysis

Analyze logged sleep, soreness, fatigue, and performance trends to
suggest training adjustments, building on the manual recovery notes in
the MVP.

### Device Integrations

Sync steps, workouts, and other activity data from wearables and
health platforms instead of relying only on manual entry.

### Budget- and Country-Based Nutrition

Recommend practical foods and meals based on the user's location,
budget, dietary preferences, and local food availability.

### Challenges and Gamification

Expand on the MVP's basic streaks and badges with optional weekly
challenges and community challenges. Keep the experience supportive and
avoid encouraging unsafe exercise or restrictive eating.

These are future website features, not reasons to expand the current
project into a mobile app.

## 6. UI and Design Direction

Create a distinctive, polished, sport-oriented interface.

Design principles:

-   Modern, clean, energetic, and premium.
-   Strong typography and clear visual hierarchy.
-   Consistent spacing, components, and navigation.
-   Attractive cards, progress indicators, and charts.
-   Thoughtful use of fitness photography and illustrations.
-   Clear loading, empty, error, and success states.
-   Accessible color contrast and keyboard navigation.
-   Responsive layouts for desktop, tablet, and mobile browsers.

All trackers (water, steps, workout timers, completion controls) must be
usable on mobile browsers, with accessible, easy-to-tap controls and
clear visual progress indicators.

Use a consistent design system with reusable buttons, form fields,
cards, navigation elements, and typography rules.

Avoid clutter, excessive gradients, generic AI-generated-looking
layouts, and unnecessary animations. Prioritize usability and
performance.

## 7. Suggested Database Structure

Inspect the existing project before creating or modifying models. Use
appropriate Django models and PostgreSQL relationships.

Potential entities include:

-   `User` --- account and authentication information.
-   `UserProfile` --- fitness profile, preferences, goals, units, and
    hydration and step targets.
-   `Food` --- food names and nutritional values per defined quantity.
-   `MealEntry` --- food diary records and serving quantities.
-   `WorkoutPlan` --- personalized training plans, including planned rest
    days.
-   `WorkoutSession` --- completed workouts and dates.
-   `Exercise` --- exercise descriptions, technique and breathing
    guidance, common mistakes, demonstration media, target muscles,
    equipment, variations, default rest, and progression details.
-   `ExerciseLog` --- completed sets, repetitions, duration or holds,
    rest taken, and effort (RPE/RIR).
-   `ProgressEntry` --- weight and optional body measurements.
-   `WaterLog` --- water intake entries with date and amount.
-   `StepLog` --- daily step counts.
-   `RecoveryNote` --- optional sleep, soreness, fatigue, and perceived
    recovery notes.
-   `Badge` / `UserBadge` --- milestone definitions and earned badges.
-   `Post` --- community text and metadata.
-   `PostImage` --- references to uploaded media.
-   `Comment` --- comments and replies.
-   `Like` --- reactions to posts.
-   `Follow` --- relationships between users.
-   `Report` --- reports for moderation.

Use foreign keys, uniqueness constraints, indexes, timestamps, and
database migrations appropriately.

Avoid duplicating data unnecessarily. Store calculated values only when
there is a clear reason to preserve historical results.

## 8. Security and Privacy

Security must be part of the initial implementation.

Requirements:

-   Use Django's authentication and password-handling features.
-   Enforce authorization on the server.
-   Protect forms and requests against CSRF where applicable.
-   Validate all user input.
-   Keep secrets in environment variables.
-   Configure production settings securely, including HTTPS, allowed
    hosts, and secure cookies where applicable.
-   Apply appropriate rate limits to expensive AI endpoints and other
    abuse-prone actions.
-   Validate image uploads and restrict file size and type.
-   Avoid exposing private profile information, including health,
    recovery, and body-measurement data.
-   Provide clear handling of user-generated content.
-   Avoid logging passwords, API keys, or unnecessary personal
    information.
-   Document required environment variables in `.env.example` without
    real secrets.

Treat nutrition, hydration, activity, recovery, and fitness guidance as
general informational support, not medical diagnosis or treatment.
Encourage professional advice where individual medical needs are
involved.

## 9. Code Quality and Testing

Write maintainable, readable code.

Requirements:

-   Keep business logic separate from views and templates.
-   Use reusable templates and components.
-   Add server-side validation.
-   Handle errors gracefully.
-   Use migrations rather than manually changing database schemas.
-   Add tests for calculations, authentication, permissions, AI response
    handling, food logging, workout functionality, timers, water and
    step tracking, streak rules, and community actions.
-   Test responsive layouts and essential user flows.
-   Do not hardcode API keys, passwords, or production credentials.
-   Avoid fake functionality and placeholder buttons presented as
    complete features.

Keep calculations such as calorie and macro targets, hydration goals,
timers, progress totals, and streak rules in deterministic application
logic with automated tests. Use AI for language-based assistance, not
as the sole source of mathematical calculations.

## 10. Development Roadmap

Build the project in stages. Implement core functionality first:
workout instructions and timers, saved performance, profile and
progress dashboard, water and step tracking, and basic streaks. Treat
advanced device integrations and automated recovery analysis as later
enhancements.

### Phase 1 --- Repository Review and Foundation

-   Inspect the existing files, dependencies, and project structure.
-   Identify what already works and what is missing.
-   Update this project brief if the existing implementation requires
    justified adjustments.
-   Propose a clear implementation plan before major changes.
-   Establish the Django application, database configuration, base
    templates, responsive design system, and environment configuration.

### Phase 2 --- Authentication and Profiles

-   Implement registration, login, logout, and profile editing.
-   Build the onboarding flow.
-   Validate and store user preferences securely.

### Phase 3 --- Nutrition Core and Daily Dashboard

-   Implement BMI, BMR, TDEE, calorie, and macro calculations.
-   Build food search and meal logging.
-   Add the water tracker and manual step tracker with personalized,
    adjustable goals.
-   Create the daily dashboard, daily and weekly summaries, and
    progress charts.

### Phase 4 --- Workout Planning and Guided Sessions

-   Implement exercise data (instructions, breathing guidance, common
    mistakes, demonstrations, variations) and workout generation rules.
-   Build personalized calisthenics plans with planned rest days.
-   Build the guided workout view: warm-up, rest countdown timer,
    completion controls, performance logging, and cool-down.
-   Add training history, recovery notes, and progression
    recommendations based on logged performance.

### Phase 5 --- Habits and Motivation

-   Implement streak rules (respecting planned rest days), weekly goals,
    milestones, and badges.
-   Connect them to the profile and progress dashboards.

### Phase 6 --- Gemini Integration

-   Connect Gemini securely through Django.
-   Add natural-language food logging.
-   Validate structured AI responses and provide clearly labeled,
    editable estimates.
-   Add clear error handling and usage limits.

### Phase 7 --- Community

-   Implement posts, image uploads, profiles, likes, comments, and
    following.
-   Add reporting and authorization checks.
-   Build public and followed-user feeds.

### Phase 8 --- Polish and Deployment

-   Test core workflows and permissions.
-   Improve mobile-browser responsiveness and accessibility.
-   Resolve errors and remove incomplete UI elements.
-   Configure production deployment and environment variables.
-   Document local setup, testing, and deployment.

Complete and test each stage before moving to the next. If the project
already contains working functionality, preserve it unless a change is
necessary.

## 11. MVP Acceptance Criteria

The first release is ready when:

-   Users can register, sign in, and edit their profiles.
-   Users can calculate and view their nutrition targets.
-   Users can log foods with editable quantities and nutrition values.
-   Users can view daily calorie and macro totals.
-   Users can track water intake and steps against adjustable goals.
-   Users can generate personalized calisthenics workouts with planned
    rest days.
-   Users can follow a guided workout with warm-up, instructions, rest
    timer, and performance logging, and mark it complete.
-   Users can record optional recovery notes and receive gradual
    progression recommendations.
-   Users can review basic progress, training history, and streaks.
-   Users can use the Gemini-powered food logging feature when the API
    is configured.
-   Users can publish community posts and images.
-   Users can like and comment on posts and follow other users.
-   Server-side permissions prevent unauthorized modifications.
-   Core features and calculations have meaningful automated tests.
-   The website works on desktop and mobile browsers.
-   Setup and deployment instructions are documented.

## 12. Instructions for Claude Code

Act as a senior full-stack engineer and product-minded technical
partner.

Before writing code:

1.  Inspect the repository and understand the current implementation.
2.  Read this file completely.
3.  Identify existing functionality that should be preserved.
4.  Explain the proposed architecture and implementation steps.
5.  Identify technical risks, especially Django, Supabase PostgreSQL,
    Gemini API, exercise demonstration media sources, and deployment
    compatibility.

While implementing:

-   Build a functional website, not just a visual prototype.
-   Prioritize a polished MVP over a large collection of incomplete
    features.
-   Keep the code modular, secure, and testable.
-   Explain significant technical decisions in plain language.
-   Run relevant tests and fix failures before claiming completion.
-   Do not claim a feature works unless it has actually been implemented
    and checked.
-   Ask for clarification only when a decision materially affects the
    implementation and cannot be reasonably inferred from this brief.

**Scope restriction:** This project is a responsive website only. Do not
build native mobile apps or add mobile-app frameworks. Keep future
enhancements separate from the MVP.

**Primary objective:** Deliver a reliable, attractive fitness and
nutrition website that combines practical tools, guided workouts,
personalized guidance, and a global community in one coherent
experience.
