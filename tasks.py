# pylint: disable=dangerous-default-value

import inspect
import os
import shlex
import sys
from datetime import datetime
from io import StringIO
from shutil import which
from textwrap import dedent

from invoke import task
from invoke.context import Context
from rich.console import Console
from subprocess import check_output


console = Console()

git_top_level = (
    check_output(
        "git rev-parse --show-toplevel", shell=True
    )
    .decode()
    .strip()
)


@task(aliases=["p"])
def preview(
    ctx: Context,
    port: str = "",
    args_: list[str] = [],
    file_: str = "slides.qmd",
):
    """Preview slides in revealjs format"""
    args = " ".join(args_)
    if which("entr"):
        console.print(
            "[bold]entr[/bold] found, hot reloading after crash enabled ✨"
        )
        ctx.run(
            f"echo {file_} | entr -c direnv exec . quarto preview /_ --render revealjs --port $PORT"
        )
    else:
        ran = ctx.run(
            f"direnv exec . quarto preview {file_} --render revealjs --port $PORT {args}",
            env={"PORT": port or os.getenv("PORT")},
            warn=True,
        )
        if not ran.ok:
            console.print(
                "😞 quarto preview crashed, please launch again"
            )


@task(aliases=["c"])
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


@task(aliases=["l"])
def litellm_model_ollama(ctx: Context):
    """List models installed with Ollama"""

    def f():
        import ollama

        model_names = [
            f"ollama/{m.model}"
            for m in ollama.list()["models"]
        ]
        print(*model_names, sep="\n")

    code_lines = inspect.getsource(f).splitlines()[1:]
    code_body = dedent("\n".join(code_lines))
    ctx.run("uv run python", in_stream=StringIO(code_body))


@task(aliases=["i"])
def ipython(ctx: Context):
    """Launch IPython shell installed via UV."""
    command = "uv run ipython --ext rich"
    argv = shlex.split(command)
    cmd = argv[0]
    os.execvp(cmd, argv)


# @task(autoprint=True)
# def length(ctx: Context, input_="messages.json", model="granite-code:20b"):
#     if not model:
#         sys.exit("model not defined")
#     content = Path(input_).read_text()
#     resp = httpx.post(
#         "http://localhost:11434/api/embeddings",
#         json={"model": model, "prompt": content},
#     )
#     resp.raise_for_status()
#     return resp


@task(aliases=["d"])
def slide_code_debug_in_ipython(
    ctx: Context, file="slides.qmd", exec_=True
):
    """QMD -> IPYNB ; ipython --pdb ..."""
    with ctx.cd(git_top_level):
        ctx.run(
            "quarto convert slides.qmd --output ipynb/slides.ipynb"
        )
        cmd = "direnv exec . uv run ipython --pdb --ext rich ipynb/slides.ipynb"
        if not exec_:
            ctx.run(
                cmd,
                pty=True,
            )
        else:
            argv = shlex.split(cmd)
            cmd = argv[0]
            os.chdir(git_top_level)
            os.execvp(cmd, argv)


@task()
def publish(ctx: Context):
    """Publish to GH pages"""
    ctx.run(
        """
        quarto render slides.qmd --to revealjs;
        rm -rf _site/minidev*;
        quarto publish gh-pages --no-prompt --no-render
        """,
        env={"PRE_COMMIT_ALLOW_NO_CONFIG": "1"},
    )


@task(aliases=["j"])
def jupyter(ctx: Context):
    with ctx.cd(git_top_level):
        ctx.run("uv run jupyter lab ", pty=True)
