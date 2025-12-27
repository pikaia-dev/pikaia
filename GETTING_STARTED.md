# Getting Started

## Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager)
- PostgreSQL 16+ (`brew install postgresql@16`)

## Local Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/TangoAgency/tango-django-ninja-stytch-saas-starter.git
cd tango-django-ninja-stytch-saas-starter

# 2. PostgreSQL setup
brew services start postgresql@16
# Add PostgreSQL binaries to PATH (add to ~/.zshrc for persistence)
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createuser -s postgres 2>/dev/null || true       # Create postgres superuser (if missing)
psql -U postgres -c "ALTER USER postgres PASSWORD 'postgres';"
createdb -U postgres tango

# 3. Backend setup (creates .venv automatically)
cd backend
uv sync                    # Creates isolated .venv, installs deps
uv run python manage.py migrate
uv run python manage.py runserver
# Backend runs at http://localhost:8000

# 4. Frontend setup (in a new terminal)
cd frontend
pnpm install
pnpm dev
# Frontend runs at http://localhost:5173

# 5. Email templates (optional, in a new terminal)
cd emails
pnpm install
pnpm dev
# Email preview at http://localhost:3000
```

## Environment Variables

```bash
cp .env.example backend/.env
# Edit backend/.env with your API keys
```

## Running Commands

Always use `uv run` to ensure commands run in the virtual environment:

```bash
cd backend
uv run pytest                      # Run tests
uv run ruff check .                # Lint
uv run ruff format .               # Format
uv run python manage.py <command>  # Any Django command
```

## Adding shadcn-ui Components

```bash
cd frontend
pnpm dlx shadcn@latest add button dialog form
```
