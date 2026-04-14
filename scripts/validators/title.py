"""Title validation functions for the AIPCC linter."""

import re

from config import (
    JIRA_PATTERN, JIRA_INTERNAL_PATTERN, SIGNED_OFF_BY_PATTERN, REVERT_PATTERN,
    MIN_TITLE_DESCRIPTION_LENGTH, MIN_TITLE_DESCRIPTION_WORDS, ValidationResult,
)


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


def validate_title_format(title: str) -> ValidationResult:
    """
    Validate strict title formatting rules.

    Valid formats:
    - "JIRA-123: description"
    - "JIRA-1, JIRA-2: description"
    - "INTERNAL: description"
    - 'Revert "JIRA-123: original title"' (validated by extracting the inner title)

    Rules enforced:
    1. Must have colon separating ticket from description
    2. Exactly one space after colon (not "JIRA-1:description" or "JIRA-1 : description")
    3. No space before colon
    4. Comma-separated tickets must have space after comma ("JIRA-1, JIRA-2" not "JIRA-1,JIRA-2")
    5. Description must be at least 10 characters OR 3 words

    Args:
        title: Title text to validate

    Returns:
        ValidationResult with success or failure
    """
    # Handle revert commits: GitLab auto-generates titles like Revert "JIRA-123: original title"
    # Extract and validate the original title instead, since it was already validated when first committed
    revert_match = REVERT_PATTERN.match(title)
    if revert_match:
        return validate_title_format(revert_match.group(1))

    # Check if title has INTERNAL or Jira ticket
    if not has_jira_ticket(title) and not has_internal_keyword(title):
        return ValidationResult.fail(
            "Title must start with a Jira ticket (e.g., RHELAI-1234) or INTERNAL"
        )

    # Check for colon
    if ':' not in title:
        return ValidationResult.fail(
            "Title must have a colon ':' separating the ticket ID from description\n"
            "Example: 'AIPCC-123: Fix authentication bug'"
        )

    # Split on first colon
    parts = title.split(':', 1)
    if len(parts) != 2:
        return ValidationResult.fail(
            "Title must have exactly one colon separating ticket from description"
        )

    ticket_part = parts[0]
    description_part = parts[1]

    # Check for space before colon (trailing space in ticket_part)
    if ticket_part.endswith(' '):
        return ValidationResult.fail(
            f"Title must not have space before colon\n"
            f"Invalid: '{ticket_part}:...'\n"
            f"Valid: '{ticket_part.strip()}:...'"
        )

    # Check for proper space after colon
    if not description_part.startswith(' '):
        return ValidationResult.fail(
            f"Title must have exactly one space after colon\n"
            f"Invalid: '{ticket_part}:{description_part}'\n"
            f"Valid: '{ticket_part}: {description_part.lstrip()}'"
        )

    # Check for multiple spaces after colon
    if description_part.startswith('  '):
        return ValidationResult.fail(
            f"Title must have exactly one space after colon (found multiple spaces)\n"
            f"Invalid: '{ticket_part}:{description_part}'\n"
            f"Valid: '{ticket_part}: {description_part.lstrip()}'"
        )

    # Check comma-separated tickets have space after comma
    if ',' in ticket_part:
        # Check for missing space after comma
        if ',,' in ticket_part or re.search(r',[A-Z]', ticket_part):
            return ValidationResult.fail(
                f"Multiple ticket IDs must have space after comma\n"
                f"Invalid: '{ticket_part}'\n"
                f"Valid: Separate tickets with ', ' (comma and space)"
            )

    # Validate description length and word count
    description = description_part.strip()

    # Check if description exists
    if not description:
        return ValidationResult.fail(
            "Title must have a description after the colon\n"
            "Example: 'AIPCC-123: Fix authentication bug'"
        )

    # Check description length
    description_length = len(description)
    description_words = len(description.split())

    if description_length < MIN_TITLE_DESCRIPTION_LENGTH and description_words < MIN_TITLE_DESCRIPTION_WORDS:
        return ValidationResult.fail(
            f"Title description is too short ('{description}')\n"
            f"Description must be at least {MIN_TITLE_DESCRIPTION_LENGTH} characters "
            f"OR at least {MIN_TITLE_DESCRIPTION_WORDS} words\n"
            f"Example: 'AIPCC-123: Fix authentication bug' (3 words, clear and concise)"
        )

    return ValidationResult.ok()
