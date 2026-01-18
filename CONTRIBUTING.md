# Contributing

Guidelines for Tango teams and AI agents.

## Commit Format

Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <description>
```

**Types**: `feat` | `fix` | `docs` | `chore` | `refactor`

**Examples**:
```
feat(auth): add magic link authentication
fix(billing): correct proration calculation
docs: update architecture decisions
chore(deps): upgrade Django to 5.0
refactor(api): extract pagination logic
```

**Breaking changes**: Add `!` after type/scope → `feat(api)!: change auth header format`

## Branching Strategy

- **Main Branch**: `main` (production-ready)
- **Feature Branches**: `feat/<name>`, `fix/<name>`, `chore/<name>` (branched from `main`)
- **Strategy**: Trunk-Based Development (short-lived branches, frequent merges)
    - *Exception*: Direct commits to `main` allowed during initial "vibe coding" / prototyping phase.

## Pull Requests

- **Target**: `main`
- **Merge Strategy**: **Merge Commit** (preserve individual commits; do not squash-and-merge)
- **Requirements**:
    - CI checks passed
    - 1 approval required (human or designated AI reviewer)
    - Clean commit history (rebase interactive before merging if necessary)

## Git Safety (AI Agents)

**NEVER use these commands:**
- `git reset` — Do not unstage or reset commits. If you staged wrong files, commit what's ready and fix in the next commit.
- `git rebase -i` — Interactive rebase requires manual input.
- `git push --force` — Never force push unless explicitly requested.
- `git clean -fd` — Deletes untracked files irreversibly.

**Instead:**
- Stage specific files with `git add <file>` rather than `git add -A` if unsure.
- Make small, focused commits. It's fine to have multiple commits.
- If you made a mistake, make a new commit to fix it — don't try to rewrite history.

## Code Style

See [rules.md](./RULES.md) for detailed coding standards.

## AI Agent Configuration

This project uses a unified `.agent/` directory for AI coding assistant configuration:

```
.agent/
├── AGENTS.md      # Main agent instructions
├── commands/      # Custom slash commands
├── rules/         # Coding standards (auto-loaded by agents)
├── settings.json  # Agent settings
└── skills/        # Reusable skill definitions
```

### Tool-Specific Symlinks

The `.claude/` directory contains symlinks to `.agent/` for Claude Code compatibility:

```
.claude/
├── CLAUDE.md     -> ../.agent/AGENTS.md
├── commands      -> ../.agent/commands
├── rules         -> ../.agent/rules
├── settings.json -> ../.agent/settings.json
└── skills        -> ../.agent/skills
```

### Editing Guidelines

**Always edit files in `.agent/`** - the source of truth. Changes propagate automatically via symlinks to tool-specific directories.

Do NOT edit files directly in `.claude/` or other tool directories - your changes will be overwritten or cause conflicts.
