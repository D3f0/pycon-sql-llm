import os
from shutil import which
import sys
from invoke import task
from invoke.context import Context
from datetime import datetime


@task()
def preview(ctx: Context, port: str = "$PORT"):
    """Build slides"""
    if which("entr"):
        print("Not using entr for reload")
    ctx.run(
        "quarto preview --render revealjs --port $PORT", env={"PORT": os.getenv("PORT")}
    )


@task()
def publish(ctx: Context):
    """Publish slides"""
    ctx.run("quarto publish gh-pages --no-prompt")


@task()
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
