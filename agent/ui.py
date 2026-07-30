"""
Console UI
"""

from rich.console import Console

console = Console()


def welcome():

    console.rule(
        "[bold blue]Vellora Therapeutics AI Assistant[/bold blue]"
    )

    console.print(
        "Connected to Gemini + MCP Server",
        style="green",
    )

    console.print()


def user_input():

    return console.input(
        "[bold cyan]You[/bold cyan] > "
    )


def assistant_output(text):

    console.print()

    console.rule("[green]Assistant[/green]")

    console.print(text)

    console.print()


def info(text):

    console.print(
        text,
        style="cyan",
    )


def success(text):

    console.print(
        text,
        style="green",
    )


def warning(text):

    console.print(
        text,
        style="yellow",
    )


def error(text):

    console.print(
        text,
        style="red",
    )
