import os
import subprocess
import sys
import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".prism"
CONFIG_PATH = CONFIG_DIR / "config.toml"

_DEFAULT_CONFIG = """\
[auth]
token = ""  # or use GITHUB_TOKEN env var

[display]
refresh_seconds = 30
max_prs = 20
max_inbox = 20
max_ci_runs = 15

[repos]
# optional: pin specific repos. if empty, auto-discovers from recent activity
watched = []
# example: watched = ["myorg/backend", "myorg/frontend"]
"""


class Config:
    def __init__(self):
        self.token: str = ""
        self.refresh_seconds: int = 30
        self.max_prs: int = 20
        self.max_inbox: int = 20
        self.max_ci_runs: int = 15
        self.watched: list[str] = []

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()

        if not CONFIG_PATH.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(_DEFAULT_CONFIG)
            print(f"Created config at {CONFIG_PATH}")

        try:
            with CONFIG_PATH.open("rb") as f:
                raw = tomllib.load(f)
        except Exception as e:
            print(f"prism: failed to parse {CONFIG_PATH}: {e}", file=sys.stderr)
            raw = {}

        auth = raw.get("auth") or {}
        display = raw.get("display") or {}
        repos = raw.get("repos") or {}

        cfg.token = auth.get("token") or ""
        cfg.refresh_seconds = int(display.get("refresh_seconds", 30))
        cfg.max_prs = int(display.get("max_prs", 20))
        cfg.max_inbox = int(display.get("max_inbox", 20))
        cfg.max_ci_runs = int(display.get("max_ci_runs", 15))
        cfg.watched = list(repos.get("watched") or [])

        # priority: env var > config file > gh CLI keyring
        env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if env_token:
            cfg.token = env_token
        elif not cfg.token:
            cfg.token = _gh_cli_token()

        return cfg


def _gh_cli_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def require_token(cfg: Config) -> str:
    if cfg.token:
        return cfg.token
    print(
        "prism: no GitHub token found.\n"
        "Options:\n"
        "  1. gh auth login  (uses existing gh CLI)\n"
        "  2. export GITHUB_TOKEN=ghp_...\n"
        "  3. add to ~/.prism/config.toml:\n\n"
        "       [auth]\n"
        '       token = "ghp_..."\n\n'
        "Required scopes: repo, read:user",
        file=sys.stderr,
    )
    sys.exit(1)
