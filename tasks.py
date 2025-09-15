from invoke import task
from invoke.context import Context


@task()
def preview(ctx: Context):
    """Build slides"""
    ctx.run("quarto preview --render revealjs --port $PORT")
    
@task()
def publish(ctx: Context):
    """Build slides"""
    ctx.run("quarto publish gh-pages --no-prompt")
