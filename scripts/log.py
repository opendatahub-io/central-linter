"""Logging setup and error output for the AIPCC linter."""

import logging
import sys

try:
    from colorama import Fore, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


def setup_logging() -> logging.Logger:
    """Configure logging for the script."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()


def error(message: str) -> None:
    """Print error message to stderr with red color if available."""
    if HAS_COLOR:
        print(Fore.RED + message, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
