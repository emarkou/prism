# prism

GitHub dashboard in your terminal — four live tiles: open PRs, inbox, CI status, contributions.

```
┌──────────────────────┬──────────────────────┐
│   MY OPEN PRS        │   INBOX              │
├──────────────────────┼──────────────────────┤
│   CI STATUS          │   CONTRIBUTIONS      │
└──────────────────────┴──────────────────────┘
```

> Screenshot placeholder

## Install

```bash
pipx install prism
```

## Setup

```bash
export GITHUB_TOKEN=ghp_yourtoken
prism
```

## Config

Config lives at `~/.prism/config.toml` (created on first run).

```toml
[auth]
token = ""  # or use GITHUB_TOKEN env var

[display]
refresh_seconds = 30
max_prs = 20
max_inbox = 20
max_ci_runs = 15

[repos]
# leave empty to auto-discover from recent activity
watched = []
# example:
# watched = ["myorg/backend", "myorg/frontend"]
```

Required token scopes: `repo`, `read:user`

## Keybindings

| Key | Action |
|-----|--------|
| `q` | quit |
| `r` | force refresh |
| `tab` | next tile |
| `shift+tab` | previous tile |
| `↑` / `k` | move up in tile |
| `↓` / `j` | move down in tile |
| `o` / `enter` | open in browser |
| `x` | dismiss inbox item (session only) |
| `m` | toggle draft (My PRs tile) |
| `?` | keybinding help overlay |
