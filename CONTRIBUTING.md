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

## Code Style

See [rules.md](./RULES.md) for detailed coding standards.
