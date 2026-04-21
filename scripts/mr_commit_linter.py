#!/usr/bin/env python3
"""
Entry point for the AIPCC MR/commit linter.

All logic lives in the sibling modules (config, main, validators/, git/, gitlab/, jira/).
This file exists solely to provide the `python3 mr_commit_linter.py` invocation used
by the Makefile in the container image.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
