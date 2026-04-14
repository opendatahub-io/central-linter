"""File content validation for the AIPCC linter."""

import os
import sys
from pathlib import Path
from typing import List, Set

from config import (
    CommitInfo, LINTERIGNORE_PATHS, POLICY_MESSAGE,
    TOOL_GENERATED_EXTENSIONS, TOOL_GENERATED_FILENAME_PATTERNS,
    ValidationResult, logger,
)
from git.commands import get_commit_modified_files


def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is binary by looking for null bytes.

    Args:
        file_path: Path to file

    Returns:
        True if file appears to be binary
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            return b'\0' in chunk
    except Exception:
        return True  # If we can't read it, treat as binary


def should_skip_newline_check(file_path: str) -> bool:
    """
    Determine if a file should be excluded from newline-at-EOF validation.

    Files are excluded if they are:
    - Non-existent (deleted files)
    - Directories
    - Symlinks (they don't have their own content)
    - Binary files (newline convention doesn't apply)
    - Tool-generated file types (e.g. .svg, .patch, .pem, .crt, .pub,
      RPM-GPG-KEY-*) where authors have no control over the trailing newline

    Args:
        file_path: Path to file to check

    Returns:
        True if file should be skipped from newline validation
    """
    # Skip if file doesn't exist (deleted)
    if not os.path.exists(file_path):
        logger.debug(f"Skipping non-existent file: {file_path}")
        return True

    # Skip directories
    if os.path.isdir(file_path):
        logger.debug(f"Skipping directory: {file_path}")
        return True

    # Skip symlinks - they don't have their own content
    if os.path.islink(file_path):
        logger.debug(f"Skipping symlink: {file_path}")
        return True

    # Skip binary files - newline convention doesn't apply
    if is_binary_file(file_path):
        logger.debug(f"Skipping binary file: {file_path}")
        return True

    # Skip tool-generated file types where trailing newlines are not expected
    path_obj = Path(file_path)
    if path_obj.suffix.lower() in TOOL_GENERATED_EXTENSIONS:
        logger.debug(f"Skipping tool-generated file type: {file_path}")
        return True
    if any(path_obj.name.startswith(pat) for pat in TOOL_GENERATED_FILENAME_PATTERNS):
        logger.debug(f"Skipping tool-generated file: {file_path}")
        return True

    return False


def validate_files_newline_at_eof(commit: CommitInfo) -> ValidationResult:
    """
    Validate that text files end with a newline character.

    Skips symlinks, binary files, directories, and deleted files.

    Args:
        commit: Commit information

    Returns:
        ValidationResult with list of files missing newline at EOF
    """
    modified_files = get_commit_modified_files(commit.commit_id)
    errors = []

    for file_path in modified_files:
        # Skip files that should be excluded from validation
        if should_skip_newline_check(file_path):
            continue

        # Check if file ends with newline
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                # Only check non-empty files
                if len(content) > 0 and not content.endswith(b'\n'):
                    errors.append(file_path)
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            continue

    if errors:
        files_str = '\n  '.join(errors)
        return ValidationResult.fail(
            f"ERROR [COMMIT {commit.commit_id}]: the following files do not end with a newline:\n"
            f"  {files_str}\n"
            f"Tip: Most editors can be configured to automatically add newlines at EOF.\n"
            f"{POLICY_MESSAGE}"
        )

    return ValidationResult.ok()


def find_linterignore_file() -> Path:
    """
    Find the linterignore file in standard locations.

    Returns:
        Path to linterignore file

    Raises:
        SystemExit if file not found
    """
    for path_func in LINTERIGNORE_PATHS:
        path = path_func()
        if path.exists():
            return path

    paths_str = [str(p()) for p in LINTERIGNORE_PATHS]
    logger.error(f"ERROR: Unable to find linterignore file in any of: {paths_str}")
    sys.exit(1)


def read_linterignore_file(file_path: Path) -> List[str]:
    """
    Read and parse the linterignore file.

    Args:
        file_path: Path to linterignore file

    Returns:
        List of file patterns/paths (excludes comments and empty lines)
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith('#')
        ]
    except PermissionError:
        logger.error(f"ERROR: No permission to read file from {file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred reading {file_path}: {e}")
        sys.exit(1)


def expand_directory_patterns(patterns: List[str]) -> Set[str]:
    """
    Expand directory patterns (e.g., "dir/*") to include all files.

    Args:
        patterns: List of file patterns

    Returns:
        Set of expanded file paths
    """
    expanded = set(patterns)

    for pattern in patterns:
        if pattern.endswith("/*"):
            directory = pattern[:-2]
            if os.path.isdir(directory):
                for dirpath, _, filenames in os.walk(directory):
                    for filename in filenames:
                        expanded.add(os.path.join(dirpath, filename))

    return expanded
