import sys
import typer

from .config import Config, require_token
from .github.client import GitHubClient
from .app import PrismApp

app = typer.Typer(add_completion=False, help="GitHub dashboard in your terminal.")


@app.command()
def main() -> None:
    cfg = Config.load()
    token = require_token(cfg)

    client = GitHubClient(token)
    PrismApp(config=cfg, client=client).run()


if __name__ == "__main__":
    app()
