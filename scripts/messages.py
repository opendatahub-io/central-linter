#!/usr/bin/env python3
"""
Helper module for linter output formatting.
"""

import sys

from colorama import Fore, init

init(autoreset=True)


def error(message) -> None:
    """Print error message to stderr with red color."""
    print(Fore.RED + message, file=sys.stderr)
