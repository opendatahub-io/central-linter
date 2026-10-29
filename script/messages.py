import sys

from colorama import Fore, init

init(autoreset=True)


def error(message) -> None:
    print(Fore.RED + message, file=sys.stderr)
