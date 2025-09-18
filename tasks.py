# pylint: disable=dangerous-default-value

from io import StringIO
import os
import shlex
from shutil import which
import sys
from textwrap import dedent
from invoke import task
from invoke.context import Context
from invoke.runners import Result
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import time
import inspect

console = Console()


@task(
    help={
        "file_path": "Path to the file to watch",
        "interval": "Check interval in milliseconds (default: 500)",
    }, 
    aliases=['w']
)
def watch(
    ctx,
    file_path,
    interval=500,
) -> bool:
    """Watch a file for changes and optionally execute a command."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/] File '{file_path}' not found")
        return

    interval_sec = interval / 1000
    last_modified = os.stat(file_path).st_mtime

    console.print(
        Panel(
            f"[bold green]Watching[/] [bold cyan]{file_path}[/] (every {interval}ms)",
            title="File Watcher",
            subtitle="Press Ctrl+C to stop",
        )
    )

    try:
        while True:
            current_modified = os.stat(file_path).st_mtime

            if current_modified != last_modified:
                timestamp = datetime.now().strftime("%H:%M:%S")
                change_text = Text(f"✨ File changed at {timestamp}")
                console.print(Panel(change_text, style="green"))
                return True

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Watcher stopped[/]")
        return False


@task(
    aliases=['p']
)
def preview(ctx: Context, port: str = "", args_: list[str] = []):
    """Build slides"""
    # if which("entr"):
    #     ctx.run(
    #         "quarto preview --render revealjs --port $PORT", env={"PORT": os.getenv("PORT")}
    #     )
    # else:
    #     print("Not using entr for reload")
    args = " ".join(args_)
    while True:
        ran = ctx.run(
            f"quarto preview --render revealjs --port $PORT {args}",
            env={"PORT": port or os.getenv("PORT")},
            warn=True,
        )
        if not ran.ok:
            print(ran.return_code)
            if not watch(ctx, file_path="slides.qmd"):
                return


@task()
def publish(ctx: Context):
    """Publish slides"""
    ctx.run("quarto publish gh-pages --no-prompt")


@task(
    aliases=['c']
)
def checkpoint(ctx: Context):
    """Checkpoint in git"""
    now = datetime.now()
    print("Creating git checkpoint...", file=sys.stderr)
    for f in ctx.run(
        r"cat slides.qmd | sed -n 's/.*!\[.*\](\([^)]*\)).*/\1/p' ",
        hide=not ctx.config.run.echo,
    ).stdout.splitlines():
        ctx.run(f"git add {f}")
    ctx.run("git add -u")

    ctx.run(f"git commit -m 'Checkpoint {now}'")


@task()
def litellm_model_ollama(ctx: Context):
    """List models installed with Ollama"""

    def f():
        import ollama

        model_names = [f"ollama/{m.model}" for m in ollama.list()["models"]]
        print(*model_names, sep="\n")

    code_lines = inspect.getsource(f).splitlines()[1:]
    code_body = dedent("\n".join(code_lines))
    ctx.run("uv run python", in_stream=StringIO(code_body))


@task(aliases=['i'])
def ipython(ctx: Context):
    """Launch IPython shell installed via UV."""
    command = "uv run ipython --ext rich"
    argv = shlex.split(command)
    cmd = argv[0]
    os.execvp(cmd, argv)
