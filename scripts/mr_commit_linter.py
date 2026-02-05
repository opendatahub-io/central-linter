#!/usr/bin/env python3
"""
Merge Request and Commit Linter for AIPCC GitLab repositories.

This script validates that commits and merge requests follow team policies:
- Commit titles must start with a Jira ticket ID or INTERNAL
- Commits must have Signed-off-by tags
- Commits must have adequate descriptions
- INTERNAL commits can only modify whitelisted files
"""

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

import requests

try:
    from colorama import Fore, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

POLICY_DOC_URL = "https://docs.google.com/document/d/1TAicyqGKKELzaYL4o-Plz2s7tFUhOctZFzHErMQSc8c"
POLICY_MESSAGE = f"See {POLICY_DOC_URL} for AIPCC Commit and Merge Request Guidelines."

# Bot usernames that are exempt from linting
BOT_NAMES = ["platform-engineering-bot", "aipcc-cicd-bot"]

# Minimum required lines in commit body (description + empty line + SOB)
MIN_COMMIT_BODY_LINES = 3

# Linterignore file search paths (in priority order)
LINTERIGNORE_PATHS = [
    lambda: Path(os.environ.get("HOME", "/home/linter")) / ".config/linterignore",
    lambda: Path("config/linterignore"),
    lambda: Path(".linterignore"),
]

# Compiled regex patterns
# Jira pattern: 2+ uppercase letters, dash, 1+ digits (e.g., RHELAI-1234, AB-1)
JIRA_PATTERN = re.compile(r"(([A-Z]{2,})-(\d+))", flags=re.MULTILINE)
JIRA_INTERNAL_PATTERN = re.compile(r"INTERNAL", flags=re.MULTILINE)
SIGNED_OFF_BY_PATTERN = re.compile(r"Signed-off-by: ", flags=re.MULTILINE)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class CommitInfo:
    """Information about a git commit."""
    commit_id: str
    title: str
    body: str


@dataclass
class MergeRequestInfo:
    """Information about a GitLab merge request."""
    iid: str
    title: str
    description: Optional[str]
    author: Optional[str]


@dataclass
class GitLabConfig:
    """GitLab API configuration from environment variables."""
    project_id: Optional[str]
    mr_iid: Optional[str]
    api_url: Optional[str]
    api_token: Optional[str]
    base_sha: str

    @classmethod
    def from_environment(cls) -> "GitLabConfig":
        """Create configuration from environment variables.

        For base_sha, checks in order:
        1. CI_MERGE_REQUEST_DIFF_BASE_SHA (GitLab CI)
        2. LINT_BASE_BRANCH (local testing override)
        3. "main" (default)
        """
        base_sha = (
            os.getenv("CI_MERGE_REQUEST_DIFF_BASE_SHA") or
            os.getenv("LINT_BASE_BRANCH") or
            "main"
        )

        return cls(
            project_id=os.getenv("CI_PROJECT_ID"),
            mr_iid=os.getenv("CI_MERGE_REQUEST_IID"),
            api_url=os.getenv("CI_API_V4_URL"),
            api_token=os.getenv("GITLAB_API_TOKEN"),
            base_sha=base_sha,
        )


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    success: bool
    error_message: Optional[str] = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(success=True)

    @classmethod
    def fail(cls, message: str) -> "ValidationResult":
        """Create a failed validation result."""
        return cls(success=False, error_message=message)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging for the script."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Only add handler if not already present (avoid duplicate handlers)
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


# ============================================================================
# GIT UTILITIES
# ============================================================================

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
    """Get detailed information about a specific commit."""
    success, body = run_git_command(["git", "log", "-1", commit_id, "--format=%b"])
    if not success:
        logger.error(f"Failed to get commit body for {commit_id}")
        sys.exit(1)

    success, title = run_git_command(["git", "log", "-1", commit_id, "--format=%s"])
    if not success:
        logger.error(f"Failed to get commit title for {commit_id}")
        sys.exit(1)

    return CommitInfo(
        commit_id=commit_id,
        title=title.strip(),
        body=body
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


# ============================================================================
# GITLAB API UTILITIES
# ============================================================================

def get_mr_author(config: GitLabConfig) -> Optional[str]:
    """
    Fetch the merge request author username from GitLab API.

    Args:
        config: GitLab configuration

    Returns:
        Author username or None if unavailable
    """
    if not config.project_id or not config.mr_iid:
        return None

    if not config.api_url or not config.api_token:
        logger.warning("GitLab API credentials not available")
        return None

    headers = {"PRIVATE-TOKEN": config.api_token}
    url = f"{config.api_url}/projects/{config.project_id}/merge_requests/{config.mr_iid}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            mr_data = response.json()
            return mr_data.get("author", {}).get("username")
        else:
            logger.warning(f"API request failed with status {response.status_code}")
    except requests.RequestException as e:
        logger.warning(f"Could not fetch MR author: {e}")

    return None


def get_mr_commits_from_api(config: GitLabConfig) -> Optional[List[str]]:
    """
    Fetch the actual list of commit SHAs in the MR from GitLab API.

    This returns only the commits that are part of the MR, not commits
    from main that were merged after the feature branch was created.

    Args:
        config: GitLab configuration

    Returns:
        List of commit SHAs in the MR, or None if unavailable
    """
    if not config.project_id or not config.mr_iid:
        return None

    if not config.api_url or not config.api_token:
        logger.warning("GitLab API credentials not available, falling back to git log")
        return None

    headers = {"PRIVATE-TOKEN": config.api_token}
    url = f"{config.api_url}/projects/{config.project_id}/merge_requests/{config.mr_iid}/commits"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            commits_data = response.json()
            # Return commit SHAs in reverse order (oldest first, like git log)
            commit_shas = [commit["id"] for commit in reversed(commits_data)]
            logger.info(f"Fetched {len(commit_shas)} commits from GitLab API for MR {config.mr_iid}")
            return commit_shas
        else:
            logger.warning(f"API request for MR commits failed with status {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.warning(f"Could not fetch MR commits from API: {e}")
        return None


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def contains_signed_off_by(text: str) -> bool:
    """
    Check if text contains a Signed-off-by tag.

    Args:
        text: Text to search

    Returns:
        True if Signed-off-by tag is present
    """
    return bool(SIGNED_OFF_BY_PATTERN.search(text))


def has_jira_ticket(text: str) -> bool:
    """
    Check if text contains a valid Jira ticket ID.

    Args:
        text: Text to search

    Returns:
        True if valid Jira ticket is present
    """
    return bool(JIRA_PATTERN.search(text))


def has_internal_keyword(text: str) -> bool:
    """
    Check if text contains the INTERNAL keyword.

    Args:
        text: Text to search

    Returns:
        True if INTERNAL keyword is present
    """
    return bool(JIRA_INTERNAL_PATTERN.search(text))


def validate_commit_title(commit: CommitInfo) -> ValidationResult:
    """
    Validate that commit title starts with Jira ticket or INTERNAL.

    Args:
        commit: Commit information

    Returns:
        ValidationResult
    """
    if has_jira_ticket(commit.title):
        return ValidationResult.ok()

    if has_internal_keyword(commit.title):
        return ValidationResult.ok()

    return ValidationResult.fail(
        f"ERROR [COMMIT {commit.commit_id}]: title must begin with a valid Jira ticket "
        f"(format: PROJECT-123, e.g., RHELAI-1234) or INTERNAL.\n{POLICY_MESSAGE}"
    )


def validate_commit_signed_off_by(commit: CommitInfo) -> ValidationResult:
    """
    Validate that commit has a Signed-off-by tag.

    Args:
        commit: Commit information

    Returns:
        ValidationResult
    """
    if contains_signed_off_by(commit.body):
        return ValidationResult.ok()

    return ValidationResult.fail(
        f"ERROR [COMMIT {commit.commit_id}]: commit does not contain a Signed-off-by: tag.\n"
        f"{POLICY_MESSAGE}"
    )


def validate_commit_body_length(commit: CommitInfo) -> ValidationResult:
    """
    Validate that commit body has minimum required lines.

    The body must have at least:
    - One line of description
    - An empty line
    - A Signed-off-by line

    Args:
        commit: Commit information

    Returns:
        ValidationResult
    """
    body_lines = commit.body.count("\n")
    if body_lines >= MIN_COMMIT_BODY_LINES:
        return ValidationResult.ok()

    return ValidationResult.fail(
        f"ERROR [COMMIT {commit.commit_id}]: description must be at least {MIN_COMMIT_BODY_LINES} "
        f"lines in length (a description, an empty line, and a Signed-off-by:).\n{POLICY_MESSAGE}"
    )


def validate_mr_title(mr_info: MergeRequestInfo) -> ValidationResult:
    """
    Validate that MR title starts with Jira ticket or INTERNAL.

    Args:
        mr_info: Merge request information

    Returns:
        ValidationResult
    """
    if has_jira_ticket(mr_info.title):
        return ValidationResult.ok()

    if has_internal_keyword(mr_info.title):
        return ValidationResult.ok()

    return ValidationResult.fail(
        f"ERROR [MERGE REQUEST {mr_info.iid}]: title must begin with a valid Jira ticket "
        f"(format: PROJECT-123, e.g., RHELAI-1234) or INTERNAL.\n{POLICY_MESSAGE}"
    )


def validate_mr_description(mr_info: MergeRequestInfo) -> ValidationResult:
    """
    Validate MR description exists and has Signed-off-by tag.

    Args:
        mr_info: Merge request information

    Returns:
        ValidationResult
    """
    if mr_info.description is None:
        return ValidationResult.fail(
            f"ERROR [MERGE REQUEST {mr_info.iid}]: description cannot be empty.\n{POLICY_MESSAGE}"
        )

    if not contains_signed_off_by(mr_info.description):
        return ValidationResult.fail(
            f"ERROR [MERGE REQUEST {mr_info.iid}]: description does not contain a "
            f"Signed-off-by: tag.\n{POLICY_MESSAGE}"
        )

    return ValidationResult.ok()


# ============================================================================
# FILE CONTENT VALIDATION
# ============================================================================

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


# ============================================================================
# INTERNAL FILE VALIDATION
# ============================================================================

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
        List of file patterns/paths
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return [line.strip() for line in content.splitlines() if line.strip()]
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


def validate_internal_commit_files(commit: CommitInfo) -> ValidationResult:
    """Validate that INTERNAL commit only modifies whitelisted files."""
    linterignore_path = find_linterignore_file()
    patterns = read_linterignore_file(linterignore_path)
    allowed_files = expand_directory_patterns(patterns)

    logger.info(f"Files that can be modified using INTERNAL: {sorted(allowed_files)}")

    modified_files = get_commit_modified_files(commit.commit_id)

    for file_path in modified_files:
        if file_path == "config/linterignore":
            return ValidationResult.fail(
                f"ERROR [COMMIT {commit.commit_id}]: config/linterignore changes cannot be made "
                f"with INTERNAL -- a JIRA must be used to modify this file.\n{POLICY_MESSAGE}"
            )

        if file_path not in allowed_files:
            return ValidationResult.fail(
                f"ERROR [COMMIT {commit.commit_id}]: {file_path} is not in {linterignore_path}"
            )

    return ValidationResult.ok()


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

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


def validate_commit(commit: CommitInfo) -> List[str]:
    """
    Validate a single commit against all rules.

    Returns:
        List of error messages (empty if all validations pass)
    """
    logger.info(f"{commit.commit_id}:\n{commit.body}\n")
    errors = []

    result = validate_commit_title(commit)
    if not result.success:
        if has_internal_keyword(commit.title):
            result = validate_internal_commit_files(commit)
            if not result.success:
                errors.append(result.error_message)
        else:
            errors.append(result.error_message)

    result = validate_commit_signed_off_by(commit)
    if not result.success:
        errors.append(result.error_message)

    result = validate_commit_body_length(commit)
    if not result.success:
        errors.append(result.error_message)

    # Validate that text files end with newline
    result = validate_files_newline_at_eof(commit)
    if not result.success:
        errors.append(result.error_message)

    return errors


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

    # Collect all errors from both commits and merge request
    all_errors = []

    commit_errors = validate_all_commits(config)
    all_errors.extend(commit_errors)

    mr_errors = validate_merge_request()
    all_errors.extend(mr_errors)

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
