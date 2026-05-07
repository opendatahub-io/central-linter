"""Merge request validation functions for the AIPCC linter."""

import os
from typing import Dict, List

from config import (
    CLOSING_PHRASE_PATTERN, ISSUE_TYPE_CHECK_PROJECT_KEYS, JIRA_ID_EXTRACT_PATTERN,
    MergeRequestInfo, GitLabConfig, JiraConfig, POLICY_MESSAGE,
    PROTECTED_ISSUE_TYPES, SKIP_ISSUE_TYPE_CHECK_LABEL, ValidationResult,
)
from log import logger
from git_utils.commands import get_commit_info, get_commits_in_range
from gitlab.api import get_mr_commits_from_api
from jira.api import get_jira_issue_type
from validators.title import validate_title_format


def validate_mr_title(mr_info: MergeRequestInfo) -> ValidationResult:
    """
    Validate that MR title follows strict formatting rules.

    Args:
        mr_info: Merge request information

    Returns:
        ValidationResult
    """
    result = validate_title_format(mr_info.title)
    if not result.success:
        return ValidationResult.fail(
            f"ERROR [MERGE REQUEST {mr_info.iid}]: {result.error_message}\n{POLICY_MESSAGE}"
        )
    return ValidationResult.ok()


def validate_mr_description(mr_info: MergeRequestInfo) -> ValidationResult:
    """
    Validate MR description is not empty.

    Signed-off-by is intentionally not checked here:
    - The MR UI already shows who opened the request.
    - Individual commits carry their own Signed-off-by tags (checked separately).
    - CI_MERGE_REQUEST_DESCRIPTION is capped at ~2700 characters by GitLab,
      which can silently truncate long descriptions and cause false failures.

    Args:
        mr_info: Merge request information

    Returns:
        ValidationResult
    """
    if not mr_info.description or not mr_info.description.strip():
        return ValidationResult.fail(
            f"ERROR [MERGE REQUEST {mr_info.iid}]: description cannot be empty.\n{POLICY_MESSAGE}"
        )

    return ValidationResult.ok()


def validate_no_protected_type_closure(
    config: GitLabConfig, jira_config: JiraConfig
) -> List[str]:
    """
    Validate that no closing keyword + protected-type Jira ID pattern exists in the MR.

    Scans MR title, MR description, and all commit messages for patterns like
    "Fixes AIPCC-100" or "Closes AIPCC-100" where the referenced Jira issue
    is a protected type (e.g. Epic). Such patterns would cause GitLab to
    auto-transition the issue to "Done" on merge.

    The check is skipped (with a warning) when:
    - The 'skip-issue-type-check' MR label is present
    - Jira credentials are not configured
    - Running outside an MR pipeline (no CI_MERGE_REQUEST_TITLE)

    Args:
        config: GitLab API configuration (for fetching commit list)
        jira_config: Jira API configuration (for issue type lookups)

    Returns:
        List of error messages (empty if no protected type closure patterns found)
    """
    # Skip when running outside MR pipeline
    mr_title = os.getenv('CI_MERGE_REQUEST_TITLE')
    if mr_title is None:
        return []

    labels = os.getenv('CI_MERGE_REQUEST_LABELS', '')
    label_list = [label.strip() for label in labels.split(',') if label.strip()]
    if SKIP_ISSUE_TYPE_CHECK_LABEL in label_list:
        logger.warning(
            f"MR label '{SKIP_ISSUE_TYPE_CHECK_LABEL}' detected - skipping protected issue type check"
        )
        return []

    # Check Jira credentials
    if not jira_config.is_configured:
        logger.warning(
            "Jira credentials not configured (JIRA_USERNAME/JIRA_API_TOKEN) - "
            "skipping protected issue type check"
        )
        return []

    # Build list of (source, text) components to scan
    mr_description = os.getenv('CI_MERGE_REQUEST_DESCRIPTION', '')
    components = []
    if mr_title:
        components.append(('MR title', mr_title))
    if mr_description:
        components.append(('MR description', mr_description))

    # Gather commit messages
    commit_shas = get_mr_commits_from_api(config)
    if commit_shas is None:
        commit_lines = get_commits_in_range(config.base_sha)
        commit_shas = (
            [line.split(' ')[0] for line in commit_lines]
            if commit_lines else []
        )
    for sha in commit_shas:
        commit = get_commit_info(sha)
        if commit.title:
            components.append(('commit message', commit.title))
        if commit.body.strip():
            components.append(('commit message', commit.body))

    # Scan each component for closing keyword + Jira ID patterns.
    found_ids: Dict[str, List[str]] = {}
    for source, text in components:
        for match in CLOSING_PHRASE_PATTERN.finditer(text):
            ids = JIRA_ID_EXTRACT_PATTERN.findall(match.group(1))
            for jira_id in ids:
                jira_id = jira_id.upper()
                project_key = jira_id.split('-', 1)[0]
                if project_key not in ISSUE_TYPE_CHECK_PROJECT_KEYS:
                    continue
                locations = found_ids.setdefault(jira_id, [])
                if source not in locations:
                    locations.append(source)

    if not found_ids:
        return []

    # Check each matched Jira ID for protected issue type
    errors = []
    for jira_id in sorted(found_ids):
        issue_type = get_jira_issue_type(jira_id, jira_config)
        if issue_type and issue_type.lower() in PROTECTED_ISSUE_TYPES:
            locations = ', '.join(found_ids[jira_id])
            errors.append(
                f"ERROR: Closing keyword found with {issue_type} ticket {jira_id} (in {locations}).\n"
                f"Merging this MR would auto-transition {issue_type} {jira_id} to 'Done' in Jira.\n"
                f"Use 'Related to {jira_id}' or 'Ref {jira_id}' instead of closing keywords like Closes/Fixes/Resolves/Implements.\n"
                f"To bypass this check, add the '{SKIP_ISSUE_TYPE_CHECK_LABEL}' label to the MR."
            )

    return errors
