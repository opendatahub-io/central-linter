"""Main orchestration for the AIPCC MR/commit linter."""

import os
import sys
from typing import List

from config import BOT_NAMES, GitLabConfig, JiraConfig, MergeRequestInfo, error, logger
from git.commands import configure_git_safe_directory, get_commit_info, get_commits_in_range, run_git_command
from gitlab.api import get_mr_author, get_mr_commits_from_api
from validators.commit import validate_commit
from validators.merge_request import validate_mr_title, validate_mr_description, validate_no_protected_type_closure


def check_bot_exemption() -> bool:
    """
    Check if current user is a bot that should be exempt from linting.

    Returns:
        True if user is an exempt bot
    """
    config = GitLabConfig.from_environment()
    mr_author = get_mr_author(config)

    gitlab_user_login = os.getenv("GITLAB_USER_LOGIN")
    gitlab_user_name = os.getenv("GITLAB_USER_NAME")

    if gitlab_user_login in BOT_NAMES:
        logger.info(f"MR by {gitlab_user_login}, ignoring")
        return True

    if gitlab_user_name in BOT_NAMES:
        logger.info(f"MR by {gitlab_user_name}, ignoring")
        return True

    if mr_author and mr_author in BOT_NAMES:
        logger.info(f"MR by {mr_author}, ignoring")
        return True

    return False


def validate_all_commits(config: GitLabConfig) -> List[str]:
    """
    Validate all commits in the merge request.

    Uses GitLab API to get the actual MR commits when available,
    otherwise falls back to git log with base_sha.

    Args:
        config: GitLab configuration

    Returns:
        List of all error messages from all commits (empty if all pass)
    """
    # Try to get commits from GitLab API first (more accurate for MRs)
    commit_shas = get_mr_commits_from_api(config)

    if commit_shas is not None:
        # Using GitLab API - we have the exact commits in the MR
        commit_ids = commit_shas
        logger.info("Using GitLab API to get MR commits (only commits in this MR will be validated)")
    else:
        # Fallback to git log (for local development or when API unavailable)
        logger.info("Using git log to get commits (falling back from GitLab API)")
        commit_lines = get_commits_in_range(config.base_sha)

        if not commit_lines:
            logger.info("No commits to validate")
            return []

        commit_ids = [line.split(" ")[0] for line in commit_lines]

    if not commit_ids:
        logger.info("No commits to validate")
        return []

    mr_iid = os.getenv("CI_MERGE_REQUEST_IID", "(local branch)")
    logger.info(f"The commits in Merge Request {mr_iid} are:")

    # Display commit info
    for commit_id in commit_ids:
        success, title = run_git_command(["git", "log", "-1", commit_id, "--format=%h %s"])
        if success:
            logger.info(title.strip())
    logger.info("---")

    all_errors = []
    for commit_id in commit_ids:
        commit = get_commit_info(commit_id)
        errors = validate_commit(commit)
        all_errors.extend(errors)

    return all_errors


def validate_merge_request() -> List[str]:
    """
    Validate merge request title and description.

    Returns:
        List of error messages (empty if all validations pass)
    """
    mr_title = os.getenv("CI_MERGE_REQUEST_TITLE")

    if mr_title is None:
        logger.info("Running locally, skipping MR validation")
        return []

    mr_iid = os.getenv("CI_MERGE_REQUEST_IID", "(unknown)")
    mr_description = os.getenv("CI_MERGE_REQUEST_DESCRIPTION")

    mr_info = MergeRequestInfo(
        iid=mr_iid,
        title=mr_title,
        description=mr_description,
        author=None
    )

    errors = []

    result = validate_mr_title(mr_info)
    if not result.success:
        errors.append(result.error_message)

    result = validate_mr_description(mr_info)
    if not result.success:
        errors.append(result.error_message)

    return errors


def main() -> int:
    """Main entry point for the linter."""
    if check_bot_exemption():
        return 0

    configure_git_safe_directory()
    config = GitLabConfig.from_environment()
    jira_config = JiraConfig.from_environment()

    # Collect all errors from both commits and merge request
    all_errors = []

    commit_errors = validate_all_commits(config)
    all_errors.extend(commit_errors)

    mr_errors = validate_merge_request()
    all_errors.extend(mr_errors)

    # MR-level: check for closing keywords + protected Jira issue types
    type_errors = validate_no_protected_type_closure(config, jira_config)
    all_errors.extend(type_errors)

    # Display all errors at once
    if all_errors:
        logger.error("\n" + "=" * 80)
        logger.error("VALIDATION FAILED - Found the following errors:")
        logger.error("=" * 80)
        for i, error_msg in enumerate(all_errors, 1):
            error(f"\n[Error {i}/{len(all_errors)}]\n{error_msg}")
        logger.error("\n" + "=" * 80)
        logger.error(f"Total errors: {len(all_errors)}")
        logger.error("=" * 80)
        return 1

    logger.info("All validations passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
