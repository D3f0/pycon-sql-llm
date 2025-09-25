import marimo

__generated_with = "0.16.2"
app = marimo.App(width="medium")


@app.cell
def _():
    a = 10
    return (a,)


@app.cell
def _(a):
    a
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
