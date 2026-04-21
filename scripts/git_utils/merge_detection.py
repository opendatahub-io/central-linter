"""Merge commit detection logic for the AIPCC linter."""

import re
from typing import Optional

from config import CommitInfo
from log import logger
from git_utils.commands import run_git_command


def is_merge_commit(commit_id: str) -> bool:
    """
    Check if a commit is a regular merge commit (has 2+ parents).

    Args:
        commit_id: Git commit SHA

    Returns:
        True if commit has 2+ parents
    """
    success, output = run_git_command(["git", "rev-list", "--parents", "-n", "1", commit_id])
    if not success:
        logger.warning(f"Failed to check parents for {commit_id}, assuming it's not a merge")
        return False

    # Output format: "commit_sha parent1_sha parent2_sha ..."
    # Merge commits have 2+ parents (3+ items in the output)
    parents = output.strip().split()
    return len(parents) > 2


def get_cherry_pick_source(commit: CommitInfo) -> Optional[str]:
    """
    Extract the original commit SHA from a cherry-picked commit.

    Cherry-picked commits contain "(cherry picked from commit <sha>)" in the body.

    Args:
        commit: Commit information

    Returns:
        Original commit SHA if this is a cherry-pick, None otherwise
    """
    # Match: (cherry picked from commit abc123...)
    match = re.search(r'\(cherry picked from commit ([a-f0-9]+)\)', commit.body, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def is_parent_merge_commit(commit: CommitInfo) -> bool:
    """
    Check if a commit is cherry-picked from a merge commit.

    Args:
        commit: Commit information

    Returns:
        True if commit is cherry-picked from a merge commit
    """
    source_sha = get_cherry_pick_source(commit)
    if source_sha:
        return is_merge_commit(source_sha)
    return False


def should_skip_commit_validation(commit: CommitInfo) -> bool:
    """
    Check if commit validation should be skipped.

    Validation is skipped for:
    1. Regular merge commits (2+ parents)
    2. Cherry-picked merge commits (source has 2+ parents)

    Args:
        commit: Commit information

    Returns:
        True if validation should be skipped
    """
    # Check if it's a regular merge commit (2+ parents)
    if is_merge_commit(commit.commit_id):
        return True

    # Check if it's cherry-picked from a merge commit
    if is_parent_merge_commit(commit):
        return True

    return False
