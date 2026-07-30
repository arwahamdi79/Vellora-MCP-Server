from rich.console import Console

console = Console()


def welcome():

    console.rule("[bold blue]Vellora Therapeutics AI Assistant[/bold blue]")

    console.print(
        "Connected to Gemini + MCP Server\n",
        style="green"
    )


def user_input():

    return console.input("[bold cyan]You > [/bold cyan]")


def assistant_output(text):

    console.print(
        f"\n[bold green]Assistant[/bold green]\n{text}\n"
    )


def error(text):

    console.print(
        f"[bold red]{text}[/bold red]"
    )
