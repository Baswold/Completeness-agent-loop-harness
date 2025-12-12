"""
Clean, user-friendly prompt utilities with sensible defaults.
"""

from typing import Optional
from prompt_toolkit import prompt as prompt_toolkit_prompt
from prompt_toolkit.styles import Style as PTStyle


pt_style = PTStyle.from_dict({
    "prompt": "#4285f4 bold",
    "": "#ffffff",
})


def yes_no(question: str, default: bool = True) -> bool:
    """
    Ask a yes/no question with a sensible default.

    Args:
        question: The question to ask
        default: Default answer (True = yes, False = no)

    Returns:
        User's answer as boolean
    """
    default_str = "Y/n" if default else "y/N"
    full_question = f"{question} [{default_str}]: "

    while True:
        try:
            answer = prompt_toolkit_prompt(
                full_question,
                style=pt_style,
            ).strip().lower()

            if not answer:
                return default

            if answer in ("y", "yes"):
                return True
            elif answer in ("n", "no"):
                return False
            else:
                print("  Please enter 'y' or 'n'")
        except (EOFError, KeyboardInterrupt):
            print()
            return default


def confirm(message: str, default: bool = True) -> bool:
    """
    Confirm an action before proceeding.

    Args:
        message: Action to confirm
        default: Default answer

    Returns:
        True if user confirmed, False otherwise
    """
    return yes_no(f"  {message}?", default=default)


def choose(question: str, options: list, default: int = 0) -> int:
    """
    Ask user to choose from numbered options.

    Args:
        question: Question to ask
        options: List of option strings
        default: Default option index (0-based)

    Returns:
        Index of chosen option
    """
    print(f"\n  {question}")
    for i, opt in enumerate(options, 1):
        marker = " ← default" if i - 1 == default else ""
        print(f"    [{i}] {opt}{marker}")

    while True:
        try:
            choice = prompt_toolkit_prompt(
                "  Enter number: ",
                style=pt_style,
            ).strip()

            if not choice:
                return default

            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            else:
                print(f"  Please enter a number between 1 and {len(options)}")
        except ValueError:
            print(f"  Please enter a number between 1 and {len(options)}")
        except (EOFError, KeyboardInterrupt):
            print()
            return default


def text_input(prompt_text: str, default: str = "") -> str:
    """
    Get text input from user.

    Args:
        prompt_text: Text to show
        default: Default value if user presses Enter

    Returns:
        User's input or default
    """
    suffix = f" [{default}]" if default else ""
    full_prompt = f"  {prompt_text}{suffix}: "

    try:
        result = prompt_toolkit_prompt(
            full_prompt,
            style=pt_style,
        ).strip()
        return result if result else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n  {title}")
    print(f"  {'-' * len(title)}")
