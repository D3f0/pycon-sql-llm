import sys
from invoke import task
from invoke.context import Context
from datetime import datetime

@task()
def preview(ctx: Context):
    """Build slides"""
    ctx.run("quarto preview --render revealjs --port $PORT")


@task()
def publish(ctx: Context):
    """Build slides"""
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
