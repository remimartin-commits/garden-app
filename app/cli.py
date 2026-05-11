"""Unified launcher: web dashboard or terminal vibe session."""

from __future__ import annotations

import threading
import webbrowser

import typer
import uvicorn

cli = typer.Typer(
    help="Codebot: Code Llama vibe studio + RAG chat (see Web dashboard).",
    no_args_is_help=False,
)


def _run_server(host: str, port: int, open_browser: bool) -> None:
    base = f"http://{host}:{port}"
    autonomy_url = f"{base}/static/autonomy.html"
    pool_demo_url = f"{base}/demo/pool"
    if open_browser:

        def _open() -> None:
            webbrowser.open(autonomy_url)

        threading.Timer(0.8, _open).start()
    typer.echo(f"Autonomy dashboard: {autonomy_url}")
    typer.echo(f"Pool marketing demo: {pool_demo_url}")
    typer.echo("Press Ctrl+C to stop.")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


@cli.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    typer.echo("")
    typer.echo("  Codebot — Code Llama + optional RAG docs")
    typer.echo("  ----------------------------------------")
    typer.echo("  [d]  Web dashboard — generate, refine, chat (starts local server)")
    typer.echo("  [t]  Terminal — vibe quiz + refine loop (no browser)")
    typer.echo("  [q]  Quit")
    typer.echo("")
    choice = typer.prompt("Choice", default="d").strip().lower()
    if choice in ("d", "dashboard", ""):
        _run_server("127.0.0.1", 8000, open_browser=True)
    elif choice in ("t", "terminal"):
        terminal()
    elif choice in ("q", "quit"):
        raise typer.Exit(0)
    else:
        typer.echo("Unknown choice; run: python -m app.cli --help")


@cli.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8000, help="HTTP port"),
    open_browser: bool = typer.Option(
        False,
        "--open",
        "-o",
        help="Open the dashboard URL after startup",
    ),
) -> None:
    """Run the API + web UI (same process as production server)."""
    _run_server(host, port, open_browser)


@cli.command("terminal")
def terminal() -> None:
    """Interactive vibe coding in the terminal (Ollama / Code Llama)."""
    from app.interactive_vibe import run_terminal_session

    run_terminal_session()


if __name__ == "__main__":
    cli()
