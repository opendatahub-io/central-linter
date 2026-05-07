"""Commit validation functions for the AIPCC linter."""

from typing import List, Set

from config import (
    ALLOWED_EMAIL_DOMAINS, CommitInfo, EMAIL_VALIDATION_ENABLED,
    POLICY_MESSAGE, REVERT_PATTERN, SOB_EMAIL_PATTERN, ValidationResult,
)
from log import logger
from git_utils.commands import get_commit_modified_files
from git_utils.merge_detection import should_skip_commit_validation
from validators.files import find_linterignore_file, read_linterignore_file, expand_directory_patterns, validate_files_newline_at_eof
from validators.title import has_internal_keyword, validate_title_format, contains_signed_off_by


def validate_commit_title(commit: CommitInfo) -> ValidationResult:
    """
    Validate that commit title follows strict formatting rules.

    Args:
        commit: Commit information

    Returns:
        ValidationResult
    """
    result = validate_title_format(commit.title)
    if not result.success:
        return ValidationResult.fail(
            f"ERROR [COMMIT {commit.commit_id}]: {result.error_message}\n{POLICY_MESSAGE}"
        )
    return ValidationResult.ok()


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
# EMAIL VALIDATION
# ============================================================================

def extract_sob_emails(text: str) -> List[str]:
    """
    Extract email addresses from Signed-off-by lines.

    Parses lines matching `Signed-off-by: Name <email>` (case-insensitive)
    and returns the email addresses in lowercase.

    Args:
        text: Text to search (commit body or MR description)

    Returns:
        List of email addresses (lowercase)
    """
    return [email.lower() for email in SOB_EMAIL_PATTERN.findall(text)]


def is_valid_email_domain(email: str, allowed_domains: Set[str]) -> bool:
    """
    Check if an email's domain is in the allowed set.

    Args:
        email: Email address to validate
        allowed_domains: Set of allowed domain strings (lowercase)

    Returns:
        True if the domain portion matches an allowed domain
    """
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    if not domain:
        return False
    return domain in allowed_domains


def format_email_error(context: str, email: str, reason: str) -> str:
    """Build a standardised email-validation error message."""
    domains_str = ", ".join(sorted(ALLOWED_EMAIL_DOMAINS))
    return (
        f"ERROR [{context}]: {reason}\n"
        f"Email: {email}\n"
        f"Allowed domains: {domains_str}\n"
        f'Tip: Configure your git email with: \'git config user.email "name@redhat.com"\'\n'
        f"{POLICY_MESSAGE}"
    )


def format_malformed_sob_error(context: str) -> str:
    """Build an error message for SOB lines missing an angle-bracket email."""
    return (
        f"ERROR [{context}]: Signed-off-by tag found but no email address "
        f"in <> brackets could be extracted.\n"
        f"Signed-off-by must use the format: Signed-off-by: Name <email>\n"
        f"Tip: Use 'git commit -s' to automatically add a properly formatted "
        f"Signed-off-by line.\n"
        f"{POLICY_MESSAGE}"
    )


def validate_commit_email(commit: CommitInfo) -> ValidationResult:
    """
    Validate that commit author and Signed-off-by emails use allowed domains.

    Checks:
    1. Commit author email (from git metadata) must use an allowed domain.
    2. All Signed-off-by emails in the commit body must use allowed domains.
    3. If Signed-off-by tags are present but no email could be parsed, the
       tag is considered malformed.

    Disabled when `EMAIL_VALIDATION_ENABLED` is `False`.

    Args:
        commit: Commit information

    Returns:
        ValidationResult
    """
    if not EMAIL_VALIDATION_ENABLED:
        return ValidationResult.ok()

    context = f"COMMIT {commit.commit_id}"

    # Validate commit author email
    if not commit.author_email:
        return ValidationResult.fail(
            format_email_error(context, "(empty)", "commit author email is empty")
        )

    if not is_valid_email_domain(commit.author_email, ALLOWED_EMAIL_DOMAINS):
        return ValidationResult.fail(
            format_email_error(
                context,
                commit.author_email,
                "commit author email uses a domain not in the allowed list",
            )
        )

    # Validate Signed-off-by emails
    has_sob = contains_signed_off_by(commit.body)
    sob_emails = extract_sob_emails(commit.body)

    if has_sob and not sob_emails:
        return ValidationResult.fail(format_malformed_sob_error(context))

    for email in sob_emails:
        if not is_valid_email_domain(email, ALLOWED_EMAIL_DOMAINS):
            return ValidationResult.fail(
                format_email_error(
                    context,
                    email,
                    "Signed-off-by email uses a domain not in the allowed list",
                )
            )

    return ValidationResult.ok()


def validate_commit(commit: CommitInfo) -> List[str]:
    """
    Validate a single commit against all rules.

    Merge commits are automatically skipped as they are generated by GitLab
    and don't follow the same conventions as regular commits.

    This includes both:
    - Regular merge commits (2+ parents)
    - Cherry-picked merge commits (source has 2+ parents)

    Returns:
        List of error messages (empty if all validations pass)
    """
    # Skip merge commits (regular or cherry-picked)
    if should_skip_commit_validation(commit):
        logger.info(f"{commit.commit_id}: Skipping validation (merge commit)")
        return []

    logger.info(f"{commit.commit_id}:\n{commit.body}\n")
    errors = []

    # Validate title format
    result = validate_commit_title(commit)
    if not result.success:
        errors.append(result.error_message)

    if has_internal_keyword(commit.title):
        result = validate_internal_commit_files(commit)
        if not result.success:
            errors.append(result.error_message)

    # UI-generated revert commits don't include a Signed-off-by line; exempt them.
    if not REVERT_PATTERN.match(commit.title):
        result = validate_commit_signed_off_by(commit)
        if not result.success:
            errors.append(result.error_message)

    result = validate_commit_email(commit)
    if not result.success:
        errors.append(result.error_message)

    # Validate that text files end with newline
    result = validate_files_newline_at_eof(commit)
    if not result.success:
        errors.append(result.error_message)

    return errors
