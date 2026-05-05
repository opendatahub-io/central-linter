"""Git command wrappers for the AIPCC linter."""

import subprocess
import sys
from typing import List, Tuple

from config import CommitInfo
from log import logger


def run_git_command(args: List[str], check: bool = True) -> Tuple[bool, str]:
    """
    Execute a git command and return success status and output.

    Args:
        args: Git command arguments (including 'git')
        check: Whether to raise exception on failure

    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {' '.join(args)}")
        logger.error(f"Error: {e.stderr}")
        return False, e.stderr


def configure_git_safe_directory() -> None:
    """
    Configure git safe directory to allow running in mounted repos.

    This is needed when the repo is mounted in a container with different ownership.
    """
    run_git_command(["git", "config", "--global", "--add", "safe.directory", "*"], check=False)


def get_commits_in_range(base_sha: str) -> List[str]:
    """
    Get list of commit lines in the range base_sha..HEAD.

    Args:
        base_sha: Base commit SHA to compare against

    Returns:
        List of commit lines in format "SHA title"
    """
    success, output = run_git_command(["git", "log", "--oneline", "--no-merges", f"{base_sha}.."])
    if not success:
        logger.error("Failed to get commit list")
        sys.exit(1)
    return output.strip().splitlines()


def get_commit_info(commit_id: str) -> CommitInfo:
    """Get detailed information about a specific commit.

    Fetches title, author email, and body in a single git command using
    NUL byte separators to reliably split the output (the body can contain
    arbitrary text including newlines).
    """
    success, output = run_git_command(
        ["git", "log", "-1", commit_id, "--format=%s%x00%ae%x00%b"]
    )
    if not success:
        logger.error(f"Failed to get commit info for {commit_id}")
        sys.exit(1)

    parts = output.split("\x00", 2)
    return CommitInfo(
        commit_id=commit_id,
        title=parts[0].strip(),
        author_email=parts[1].strip() if len(parts) > 1 else "",
        body=parts[2] if len(parts) > 2 else "",
    )


def get_commit_modified_files(commit_id: str) -> List[str]:
    """
    Get list of files modified by a commit.

    Args:
        commit_id: Git commit SHA

    Returns:
        List of file paths
    """
    success, output = run_git_command(["git", "show", "--numstat", "--pretty=%n", commit_id])
    if not success:
        logger.error(f"Failed to get modified files for {commit_id}")
        sys.exit(1)

    files = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line == '"':
            continue

        parts = line.split()
        if len(parts) >= 3:
            files.append(parts[2])

    return files
