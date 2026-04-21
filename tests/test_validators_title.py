"""Tests for validators.title module.

Ported from TestPatternMatching and TestValidateTitleFormat in test_mr_commit_linter.py.
"""

import pytest

from config import MIN_TITLE_DESCRIPTION_LENGTH, MIN_TITLE_DESCRIPTION_WORDS
from validators.title import (
    contains_signed_off_by,
    has_jira_ticket,
    has_internal_keyword,
    validate_title_format,
)


# ============================================================================
# PATTERN MATCHING TESTS
# ============================================================================

class TestPatternMatching:
    def test_contains_signed_off_by_present(self):
        text = "Description\n\nSigned-off-by: John Doe <john@example.com>"
        assert contains_signed_off_by(text) is True

    def test_contains_signed_off_by_absent(self):
        text = "Description\n\nReviewed-by: Jane Doe"
        assert contains_signed_off_by(text) is False

    def test_contains_signed_off_by_middle_of_text(self):
        text = "Description\n\nSigned-off-by: John Doe\nReviewed-by: Jane"
        assert contains_signed_off_by(text) is True

    @pytest.mark.parametrize("ticket_id,expected", [
        ("RHELAI-1234", True),
        ("RHOAIENG-5678", True),
        ("AIPCC-999", True),
        ("INFERENG-123", True),
        ("RHAIENG-456", True),
        ("ANYPROJECT-123", True),
        ("AB-1", True),
        ("A-123", False),
        ("invalid-123", False),
        ("INVALID123", False),
        ("No ticket here", False),
    ])
    def test_has_jira_ticket(self, ticket_id, expected):
        text = f"{ticket_id}: Some commit message"
        assert has_jira_ticket(text) == expected

    def test_has_internal_keyword_present(self):
        assert has_internal_keyword("INTERNAL: Fix typo") is True

    def test_has_internal_keyword_absent(self):
        assert has_internal_keyword("Fix typo") is False


# ============================================================================
# TITLE FORMAT VALIDATION TESTS
# ============================================================================

class TestValidateTitleFormat:
    # Valid formats
    def test_valid_format_with_jira_ticket(self):
        result = validate_title_format("RHELAI-1234: Fix authentication bug")
        assert result.success is True
        assert result.error_message is None

    def test_valid_format_with_internal(self):
        result = validate_title_format("INTERNAL: Update documentation")
        assert result.success is True

    def test_valid_format_multi_ticket(self):
        result = validate_title_format("AIPCC-1, AIPCC-2: Fix multiple bugs")
        assert result.success is True

    def test_valid_format_short_but_three_words(self):
        result = validate_title_format("AB-1: Fix the bug")
        assert result.success is True

    def test_valid_format_long_description(self):
        result = validate_title_format("RHELAI-1: A very long description")
        assert result.success is True

    def test_valid_format_exactly_ten_chars(self):
        result = validate_title_format("RHELAI-1: 1234567890")
        assert result.success is True

    def test_valid_format_exactly_three_words(self):
        result = validate_title_format("RHELAI-1: One two three")
        assert result.success is True

    # Invalid formats - missing ticket/keyword
    def test_invalid_no_ticket_or_internal(self):
        result = validate_title_format("Fix authentication bug")
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    # Invalid formats - missing colon
    def test_invalid_missing_colon(self):
        result = validate_title_format("RHELAI-1234 Fix authentication bug")
        assert result.success is False
        assert "must have a colon" in result.error_message
        assert "separating the ticket ID" in result.error_message

    # Invalid formats - spacing issues with colon
    def test_invalid_no_space_after_colon(self):
        result = validate_title_format("RHELAI-1234:Fix bug")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_invalid_multiple_spaces_after_colon(self):
        result = validate_title_format("RHELAI-1234:  Fix bug")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message
        assert "multiple spaces" in result.error_message

    def test_invalid_space_before_colon(self):
        result = validate_title_format("RHELAI-1234 : Fix bug")
        assert result.success is False
        assert "must not have space before colon" in result.error_message

    # Invalid formats - comma-separated tickets
    def test_invalid_no_space_after_comma(self):
        result = validate_title_format("RHELAI-1,RHELAI-2: Fix bug")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    def test_invalid_double_comma(self):
        result = validate_title_format("RHELAI-1,, RHELAI-2: Fix bug")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    # Invalid formats - description issues
    def test_invalid_empty_description(self):
        result = validate_title_format("RHELAI-1234: ")
        assert result.success is False
        assert "must have a description after the colon" in result.error_message

    def test_invalid_only_whitespace_description(self):
        result = validate_title_format("RHELAI-1234:    \t  ")
        assert result.success is False
        assert "multiple spaces" in result.error_message or "must have a description" in result.error_message

    def test_invalid_description_too_short(self):
        result = validate_title_format("RHELAI-1234: Fix")
        assert result.success is False
        assert "description is too short" in result.error_message
        assert f"at least {MIN_TITLE_DESCRIPTION_LENGTH} characters" in result.error_message
        assert f"at least {MIN_TITLE_DESCRIPTION_WORDS} words" in result.error_message

    def test_invalid_description_two_words_short_length(self):
        result = validate_title_format("RHELAI-1: Fix it")
        assert result.success is False
        assert "description is too short" in result.error_message

    def test_invalid_description_one_short_word(self):
        result = validate_title_format("RHELAI-1: Update")
        assert result.success is False
        assert "description is too short" in result.error_message

    # Edge cases
    def test_valid_internal_with_proper_format(self):
        result = validate_title_format("INTERNAL: Update the configuration file")
        assert result.success is True

    def test_invalid_internal_no_space_after_colon(self):
        result = validate_title_format("INTERNAL:Update config")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_valid_multiple_tickets_proper_spacing(self):
        result = validate_title_format("RHELAI-1, RHOAIENG-2, AIPCC-3: Fix multiple issues")
        assert result.success is True

    def test_invalid_multiple_tickets_mixed_spacing(self):
        result = validate_title_format("RHELAI-1, RHOAIENG-2,AIPCC-3: Fix bugs")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    # Revert commit handling
    def test_valid_revert_with_jira_inner_title(self):
        result = validate_title_format('Revert "AIPCC-1234: Fix authentication bug"')
        assert result.success is True

    def test_valid_revert_with_internal_inner_title(self):
        result = validate_title_format('Revert "INTERNAL: Update documentation file"')
        assert result.success is True

    def test_valid_revert_with_multi_ticket_inner_title(self):
        result = validate_title_format('Revert "AIPCC-1, AIPCC-2: Fix multiple bugs"')
        assert result.success is True

    def test_invalid_revert_with_bad_inner_title(self):
        result = validate_title_format('Revert "Fix authentication bug"')
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_invalid_plain_revert_no_quotes(self):
        result = validate_title_format("Revert some change")
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message
