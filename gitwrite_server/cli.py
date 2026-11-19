"""Command-line entrypoint: python -m gitwrite_server / gitwrite-server."""

from pathlib import Path

import click
import waitress

from gitwrite_server.auth import InvalidTokenLabel, create_token, list_tokens, revoke_token

_DEFAULT_REPOS_ROOT = Path.home() / ".gitwrite" / "repos"
_DEFAULT_TOKENS_FILE = Path.home() / ".gitwrite" / "tokens"


@click.group()
def cli() -> None:
    """GitWrite sync server: token management and the git smart-HTTP service."""


@cli.command()
@click.argument("label")
@click.option(
    "--tokens-file",
    type=click.Path(path_type=Path),
    envvar="GITWRITE_TOKEN_FILE",
    default=_DEFAULT_TOKENS_FILE,
    show_default="~/.gitwrite/tokens (or $GITWRITE_TOKEN_FILE)",
    help="Token file to store the hash in.",
)
def create_token_command(label: str, tokens_file: Path) -> None:
    """Mint a token under LABEL and print it. The plaintext is shown exactly once."""
    try:
        token = create_token(label, tokens_file=tokens_file)
    except InvalidTokenLabel as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(token)


@cli.command()
@click.argument("label")
@click.option(
    "--tokens-file",
    type=click.Path(path_type=Path),
    envvar="GITWRITE_TOKEN_FILE",
    default=_DEFAULT_TOKENS_FILE,
    show_default="~/.gitwrite/tokens (or $GITWRITE_TOKEN_FILE)",
    help="Token file to remove the hash from.",
)
def revoke_token_command(label: str, tokens_file: Path) -> None:
    """Revoke the token stored under LABEL."""
    if revoke_token(label, tokens_file=tokens_file):
        click.echo(f"revoked: {label}")
    else:
        raise click.ClickException(f"no token labeled {label!r}")


@cli.command("list-tokens")
@click.option(
    "--tokens-file",
    type=click.Path(path_type=Path),
    envvar="GITWRITE_TOKEN_FILE",
    default=_DEFAULT_TOKENS_FILE,
    show_default="~/.gitwrite/tokens (or $GITWRITE_TOKEN_FILE)",
    help="Token file to read labels from.",
)
def list_tokens_command(tokens_file: Path) -> None:
    """List the labels of all stored tokens."""
    for label in list_tokens(tokens_file=tokens_file):
        click.echo(label)


@cli.command()
@click.option(
    "--repos-root",
    type=click.Path(path_type=Path),
    envvar="GITWRITE_REPOS_ROOT",
    default=_DEFAULT_REPOS_ROOT,
    show_default="~/.gitwrite/repos (or $GITWRITE_REPOS_ROOT)",
    help="Directory holding bare repositories.",
)
@click.option(
    "--tokens-file",
    type=click.Path(path_type=Path),
    envvar="GITWRITE_TOKEN_FILE",
    default=_DEFAULT_TOKENS_FILE,
    show_default="~/.gitwrite/tokens (or $GITWRITE_TOKEN_FILE)",
    help="Token file to authenticate against.",
)
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option("--port", default=8080, show_default=True, type=int, help="Port.")
def serve(repos_root: Path, tokens_file: Path, host: str, port: int) -> None:
    """Serve git smart HTTP over plain HTTP (TLS is the reverse proxy's job)."""
    repos_root.mkdir(parents=True, exist_ok=True)
    # Import here so token commands need not depend on the serving stack.
    from gitwrite_server.app import create_app

    app = create_app(repos_root=repos_root, tokens_file=tokens_file)
    click.echo(f"serving git repos from {repos_root} on http://{host}:{port}")
    waitress.serve(app, host=host, port=port)


def main() -> None:
    """Console entrypoint (gitwrite-server) and python -m gitwrite_server."""
    cli()


if __name__ == "__main__":
    main()
