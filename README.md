# Hoops Planner

Task planning application for basketball clubs. Assign referees, scorers, timers, and 24-second operators to games while automatically enforcing eligibility rules and distributing tasks fairly across your roster.

## Features

- **CSV Import** — upload season schedules and member lists
- **Interactive Planner** — drag-and-drop task assignment with smart candidate suggestions
- **Eligibility Rules** — automatic conflict detection (team games, age category, certification level)
- **Fair Distribution** — task counter with multipliers rewards members already at the gym
- **Statistics** — per-player and per-team task tracking with export
- **Member View** — mobile-friendly read-only view for checking upcoming duties
- **PDF Export** — print-ready schedule output
- **Auth** — password reset and email verification

## Tech Stack

| Layer      | Stack                                              |
| ---------- | -------------------------------------------------- |
| Frontend   | React 19 + TypeScript + Vite + TanStack Query      |
| Backend    | Django + DRF (Python 3.13)                         |
| Database   | SQLite (dev)                                       |
| Testing    | pytest (backend), Playwright (e2e)                 |
| Linting    | Ruff (Python), ESLint (frontend)                   |
| Type Check | ty (Python), tsc (frontend)                        |
| Packaging  | uv (Python), pnpm (frontend)                       |

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/coenvdgrinten/hoops-planner.git
cd hoops-planner

# Start the containers
docker compose up --build
```

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000/api/>

## Development

### Backend

```bash
# Create virtual environment and install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Start dev server
uv run python manage.py runserver

# Run tests
uv run pytest

# Lint and type-check
uv run ruff check src tests
uv run ty check src tests
```

### Frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Start dev server (points to backend container)
pnpm dev

# Type-check, lint, and build
pnpm check
pnpm lint
pnpm build

# Run e2e tests
pnpm test:e2e
```

## Configuration

Set via environment variables (or `.env`):

| Variable            | Default                              | Description                          |
| ------------------- | ------------------------------------ | ------------------------------------ |
| `DEBUG`             | `False`                              | Django debug mode                    |
| `SECRET_KEY`        | *(required)*                         | Django secret key                    |
| `DB_PATH`           | `/data/db.sqlite3`                   | SQLite database path                 |
| `SITE_URL`          | `http://localhost:5173`              | Base URL for email links             |
| `EMAIL_BACKEND`     | `django.core.mail.backends.console`  | Email backend for dev/prod           |
| `DEFAULT_FROM_EMAIL`| `noreply@example.com`                | Sender address for outgoing emails   |
| `VITE_API_URL`      | `http://backend:8000`                | Frontend → backend API URL           |

## Project Structure

```text
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   └── components/
│   └── e2e/
├── src/
│   └── sixth_man/
│       ├── settings.py
│       ├── urls.py
│       └── core/
│           ├── models.py
│           ├── views.py
│           ├── serializers.py
│           ├── auth_views.py
│           ├── eligibility.py
│           ├── suggestions.py
│           ├── statistics.py
│           ├── importers.py
│           └── migrations/
└── tests/
```

## Task Types

| Task                | Description                                    |
| ------------------- | ---------------------------------------------- |
| **Referee**         | 1–2 per game, configurable per age category    |
| **Scorer**          | Live scorekeeping on a tablet                  |
| **Timer**           | Physical scoreboard operator                   |
| **24s Operator**    | 24-second clock (configurable per team)        |

## Eligibility Rules

A member is ineligible if:

- Their own team has a home game at the same time
- Their own team has an away game on the same day
- For refereeing: their team is younger than the game's teams
- For refereeing: they lack the required certification level
- They're already assigned to a task in that game

Coaches are exempt from mandatory tasks but can still volunteer.

## License

Private
