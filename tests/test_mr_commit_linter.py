#!/usr/bin/env python3
"""
Unit tests for mr_commit_linter.py

Run with: pytest tests/
"""

import requests as requests_lib

import pytest
from unittest.mock import Mock, patch

from scripts.mr_commit_linter import (
    CommitInfo,
    MergeRequestInfo,
    GitLabConfig,
    JiraConfig,
    ValidationResult,
    contains_signed_off_by,
    has_jira_ticket,
    has_internal_keyword,
    validate_title_format,
    validate_commit_title,
    validate_commit_signed_off_by,
    validate_mr_title,
    validate_mr_description,
    validate_no_protected_type_closure,
    read_linterignore_file,
    expand_directory_patterns,
    is_binary_file,
    should_skip_newline_check,
    validate_files_newline_at_eof,
    get_mr_commits_from_api,
    get_jira_issue_type,
    validate_all_commits,
    validate_commit,
    is_merge_commit,
    is_parent_merge_commit,
    get_cherry_pick_source,
    CLOSING_PHRASE_PATTERN,
    JIRA_ID_EXTRACT_PATTERN,
    MIN_TITLE_DESCRIPTION_LENGTH,
    MIN_TITLE_DESCRIPTION_WORDS,
)


# ============================================================================
# PATTERN MATCHING TESTS
# ============================================================================

class TestPatternMatching:
    """Tests for regex pattern matching functions."""

    def test_contains_signed_off_by_present(self):
        """Test detection of Signed-off-by tag."""
        text = "Description\n\nSigned-off-by: John Doe <john@example.com>"
        assert contains_signed_off_by(text) is True

    def test_contains_signed_off_by_absent(self):
        """Test when Signed-off-by tag is missing."""
        text = "Description\n\nReviewed-by: Jane Doe"
        assert contains_signed_off_by(text) is False

    def test_contains_signed_off_by_middle_of_text(self):
        """Test Signed-off-by tag in middle of description."""
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
        """Test Jira ticket detection with various patterns."""
        text = f"{ticket_id}: Some commit message"
        assert has_jira_ticket(text) == expected

    def test_has_internal_keyword_present(self):
        """Test INTERNAL keyword detection."""
        assert has_internal_keyword("INTERNAL: Fix typo") is True

    def test_has_internal_keyword_absent(self):
        """Test when INTERNAL keyword is missing."""
        assert has_internal_keyword("Fix typo") is False


# ============================================================================
# TITLE FORMAT VALIDATION TESTS
# ============================================================================

class TestValidateTitleFormat:
    """Tests for strict title formatting validation."""

    # Valid formats
    def test_valid_format_with_jira_ticket(self):
        """Test valid format with JIRA ticket."""
        result = validate_title_format("RHELAI-1234: Fix authentication bug")
        assert result.success is True
        assert result.error_message is None

    def test_valid_format_with_internal(self):
        """Test valid format with INTERNAL keyword."""
        result = validate_title_format("INTERNAL: Update documentation")
        assert result.success is True

    def test_valid_format_multi_ticket(self):
        """Test valid format with multiple comma-separated tickets."""
        result = validate_title_format("AIPCC-1, AIPCC-2: Fix multiple bugs")
        assert result.success is True

    def test_valid_format_short_but_three_words(self):
        """Test valid format with short description but 3 words."""
        result = validate_title_format("AB-1: Fix the bug")
        assert result.success is True

    def test_valid_format_long_description(self):
        """Test valid format with description >= 10 characters."""
        result = validate_title_format("RHELAI-1: A very long description")
        assert result.success is True

    def test_valid_format_exactly_ten_chars(self):
        """Test valid format with exactly 10 character description."""
        result = validate_title_format("RHELAI-1: 1234567890")
        assert result.success is True

    def test_valid_format_exactly_three_words(self):
        """Test valid format with exactly 3 words."""
        result = validate_title_format("RHELAI-1: One two three")
        assert result.success is True

    # Invalid formats - missing ticket/keyword
    def test_invalid_no_ticket_or_internal(self):
        """Test invalid format without JIRA ticket or INTERNAL."""
        result = validate_title_format("Fix authentication bug")
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    # Invalid formats - missing colon
    def test_invalid_missing_colon(self):
        """Test invalid format without colon separator."""
        result = validate_title_format("RHELAI-1234 Fix authentication bug")
        assert result.success is False
        assert "must have a colon" in result.error_message
        assert "separating the ticket ID" in result.error_message

    # Invalid formats - spacing issues with colon
    def test_invalid_no_space_after_colon(self):
        """Test invalid format with no space after colon."""
        result = validate_title_format("RHELAI-1234:Fix bug")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_invalid_multiple_spaces_after_colon(self):
        """Test invalid format with multiple spaces after colon."""
        result = validate_title_format("RHELAI-1234:  Fix bug")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message
        assert "multiple spaces" in result.error_message

    def test_invalid_space_before_colon(self):
        """Test invalid format with space before colon."""
        result = validate_title_format("RHELAI-1234 : Fix bug")
        assert result.success is False
        assert "must not have space before colon" in result.error_message

    # Invalid formats - comma-separated tickets
    def test_invalid_no_space_after_comma(self):
        """Test invalid format with comma-separated tickets without space."""
        result = validate_title_format("RHELAI-1,RHELAI-2: Fix bug")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    def test_invalid_double_comma(self):
        """Test invalid format with double comma."""
        result = validate_title_format("RHELAI-1,, RHELAI-2: Fix bug")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    # Invalid formats - description issues
    def test_invalid_empty_description(self):
        """Test invalid format with empty description after colon."""
        result = validate_title_format("RHELAI-1234: ")
        assert result.success is False
        assert "must have a description after the colon" in result.error_message

    def test_invalid_only_whitespace_description(self):
        """Test invalid format with only whitespace as description."""
        result = validate_title_format("RHELAI-1234:    \t  ")
        assert result.success is False
        assert "multiple spaces" in result.error_message or "must have a description" in result.error_message

    def test_invalid_description_too_short(self):
        """Test invalid format with description too short (< 10 chars and < 3 words)."""
        result = validate_title_format("RHELAI-1234: Fix")
        assert result.success is False
        assert "description is too short" in result.error_message
        assert f"at least {MIN_TITLE_DESCRIPTION_LENGTH} characters" in result.error_message
        assert f"at least {MIN_TITLE_DESCRIPTION_WORDS} words" in result.error_message

    def test_invalid_description_two_words_short_length(self):
        """Test invalid format with 2 words and short length."""
        result = validate_title_format("RHELAI-1: Fix it")
        assert result.success is False
        assert "description is too short" in result.error_message

    def test_invalid_description_one_short_word(self):
        """Test invalid format with 1 word that is < 10 characters."""
        result = validate_title_format("RHELAI-1: Update")
        assert result.success is False
        assert "description is too short" in result.error_message

    # Edge cases
    def test_valid_internal_with_proper_format(self):
        """Test INTERNAL keyword follows same formatting rules."""
        result = validate_title_format("INTERNAL: Update the configuration file")
        assert result.success is True

    def test_invalid_internal_no_space_after_colon(self):
        """Test INTERNAL without space after colon."""
        result = validate_title_format("INTERNAL:Update config")
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_valid_multiple_tickets_proper_spacing(self):
        """Test multiple tickets with proper spacing."""
        result = validate_title_format("RHELAI-1, RHOAIENG-2, AIPCC-3: Fix multiple issues")
        assert result.success is True

    def test_invalid_multiple_tickets_mixed_spacing(self):
        """Test multiple tickets with inconsistent spacing."""
        result = validate_title_format("RHELAI-1, RHOAIENG-2,AIPCC-3: Fix bugs")
        assert result.success is False
        assert "must have space after comma" in result.error_message

    # Revert commit handling
    def test_valid_revert_with_jira_inner_title(self):
        """Test that revert commits with valid inner JIRA title pass validation."""
        result = validate_title_format('Revert "AIPCC-1234: Fix authentication bug"')
        assert result.success is True

    def test_valid_revert_with_internal_inner_title(self):
        """Test that revert commits with valid INTERNAL inner title pass validation."""
        result = validate_title_format('Revert "INTERNAL: Update documentation file"')
        assert result.success is True

    def test_valid_revert_with_multi_ticket_inner_title(self):
        """Test that revert commits with valid multi-ticket inner title pass validation."""
        result = validate_title_format('Revert "AIPCC-1, AIPCC-2: Fix multiple bugs"')
        assert result.success is True

    def test_invalid_revert_with_bad_inner_title(self):
        """Test that revert commits with invalid inner title fail validation."""
        result = validate_title_format('Revert "Fix authentication bug"')
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_invalid_plain_revert_no_quotes(self):
        """Test that a title starting with 'Revert' but without quotes is not treated as revert."""
        result = validate_title_format("Revert some change")
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message


# ============================================================================
# MERGE COMMIT TESTS
# ============================================================================

class TestMergeCommit:
    """Tests for merge commit detection and handling."""

    @patch('scripts.mr_commit_linter.run_git_command')
    def test_is_merge_commit_true(self, mock_git):
        """Test detection of regular merge commit (2 parents)."""
        # Output has 3 items: commit_sha parent1_sha parent2_sha
        mock_git.return_value = (True, "abc123 def456 ghi789\n")
        assert is_merge_commit("abc123") is True

    @patch('scripts.mr_commit_linter.run_git_command')
    def test_is_merge_commit_false(self, mock_git):
        """Test detection of regular commit (1 parent)."""
        # Output has 2 items: commit_sha parent1_sha
        mock_git.return_value = (True, "abc123 def456\n")
        assert is_merge_commit("abc123") is False

    @patch('scripts.mr_commit_linter.run_git_command')
    def test_is_merge_commit_git_failure(self, mock_git):
        """Test handling of git command failure."""
        mock_git.return_value = (False, "error")
        assert is_merge_commit("abc123") is False

    def test_get_cherry_pick_source_found(self):
        """Test extracting source commit SHA from cherry-pick message."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\n(cherry picked from commit def456789)"
        )
        assert get_cherry_pick_source(commit) == "def456789"

    def test_get_cherry_pick_source_not_found(self):
        """Test that non-cherry-picked commits return None."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        assert get_cherry_pick_source(commit) is None

    @patch('scripts.mr_commit_linter.is_merge_commit')
    def test_is_parent_merge_commit_true(self, mock_is_merge):
        """Test detection of cherry-picked merge commit."""
        # Source commit is a merge (2+ parents)
        mock_is_merge.return_value = True

        commit = CommitInfo(
            commit_id="abc123",
            title="Merge branch 'feature' into 'main'",
            body="See merge request !123\n\n(cherry picked from commit def456789)"
        )

        assert is_parent_merge_commit(commit) is True
        mock_is_merge.assert_called_once_with("def456789")

    @patch('scripts.mr_commit_linter.is_merge_commit')
    def test_is_parent_merge_commit_false(self, mock_is_merge):
        """Test that cherry-picked regular commit is not detected as parent merge."""
        # Source commit is NOT a merge (1 parent)
        mock_is_merge.return_value = False

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev\n\n(cherry picked from commit def456789)"
        )

        assert is_parent_merge_commit(commit) is False
        mock_is_merge.assert_called_once_with("def456789")

    def test_is_parent_merge_commit_not_cherry_picked(self):
        """Test that non-cherry-picked commits return False."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )

        assert is_parent_merge_commit(commit) is False

    @patch('scripts.mr_commit_linter.should_skip_commit_validation')
    def test_validate_commit_skips_merge(self, mock_should_skip):
        """Test that merge commits are skipped during validation."""
        mock_should_skip.return_value = True

        commit = CommitInfo(
            commit_id="abc123",
            title="Merge branch 'feature' into 'main'",
            body="See merge request !123"  # No Signed-off-by
        )

        errors = validate_commit(commit)
        assert errors == []  # No errors, merge commit was skipped
        mock_should_skip.assert_called_once_with(commit)

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    @patch('scripts.mr_commit_linter.should_skip_commit_validation')
    def test_validate_commit_validates_regular(self, mock_should_skip, mock_get_files):
        """Test that regular commits are validated normally."""
        mock_should_skip.return_value = False
        mock_get_files.return_value = []  # No files modified

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Short"  # Missing SOB, too short
        )

        errors = validate_commit(commit)
        assert len(errors) > 0  # Should have validation errors
        mock_should_skip.assert_called_once_with(commit)


# ============================================================================
# COMMIT VALIDATION TESTS
# ============================================================================

class TestCommitValidation:
    """Tests for commit validation functions."""

    def test_validate_commit_title_with_jira(self):
        """Test commit title validation with valid Jira ticket."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix authentication bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True
        assert result.error_message is None

    def test_validate_commit_title_with_internal(self):
        """Test commit title validation with INTERNAL keyword."""
        commit = CommitInfo(
            commit_id="abc123",
            title="INTERNAL: Update documentation",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True

    def test_validate_commit_title_invalid(self):
        """Test commit title validation with invalid title (no ticket)."""
        commit = CommitInfo(
            commit_id="abc123",
            title="Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message
        assert result.error_message is not None

    def test_validate_commit_title_invalid_no_colon(self):
        """Test commit title validation missing colon separator."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234 Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must have a colon" in result.error_message

    def test_validate_commit_title_invalid_no_space_after_colon(self):
        """Test commit title validation with no space after colon."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234:Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_validate_commit_title_revert_with_valid_inner_title(self):
        """Test commit title validation for GitLab auto-generated revert commit."""
        commit = CommitInfo(
            commit_id="abc123",
            title='Revert "AIPCC-1234: Fix authentication bug"',
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True

    def test_validate_commit_title_revert_with_invalid_inner_title(self):
        """Test commit title validation for revert commit with invalid inner title."""
        commit = CommitInfo(
            commit_id="abc123",
            title='Revert "Fix authentication bug"',
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_commit_signed_off_by_present(self):
        """Test Signed-off-by validation when tag is present."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Description of changes\n\nSigned-off-by: John Doe <john@example.com>"
        )
        result = validate_commit_signed_off_by(commit)
        assert result.success is True

    def test_validate_commit_signed_off_by_missing(self):
        """Test Signed-off-by validation when tag is missing."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Description of changes"
        )
        result = validate_commit_signed_off_by(commit)
        assert result.success is False
        assert "does not contain a Signed-off-by" in result.error_message


# ============================================================================
# MERGE REQUEST VALIDATION TESTS
# ============================================================================

class TestMergeRequestValidation:
    """Tests for merge request validation functions."""

    def test_validate_mr_title_with_jira(self):
        """Test MR title validation with valid Jira ticket."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Feature implementation",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_with_internal(self):
        """Test MR title validation with INTERNAL keyword."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="INTERNAL: Documentation update",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_invalid(self):
        """Test MR title validation with invalid title (no ticket)."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="Feature implementation",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_mr_title_invalid_no_colon(self):
        """Test MR title validation missing colon separator."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234 Feature implementation",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must have a colon" in result.error_message

    def test_validate_mr_title_invalid_short_description(self):
        """Test MR title validation with too short description."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Fix",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "description is too short" in result.error_message

    def test_validate_mr_title_revert_with_valid_inner_title(self):
        """Test MR title validation for GitLab auto-generated revert MR."""
        mr_info = MergeRequestInfo(
            iid="123",
            title='Revert "AIPCC-1234: Fix authentication bug"',
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_revert_with_invalid_inner_title(self):
        """Test MR title validation for revert MR with invalid inner title."""
        mr_info = MergeRequestInfo(
            iid="123",
            title='Revert "Fix authentication bug"',
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_mr_description_valid(self):
        """Test MR description validation with valid description."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Fix",
            description="This is a description\n\nSigned-off-by: John Doe <john@example.com>",
            author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is True

    def test_validate_mr_description_empty(self):
        """Test MR description validation when description is None."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Fix",
            description=None,
            author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is False
        assert "description cannot be empty" in result.error_message

    def test_validate_mr_description_missing_signed_off_by(self):
        """Test MR description validation without Signed-off-by tag."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Fix",
            description="This is a description",
            author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is False
        assert "does not contain a Signed-off-by" in result.error_message


# ============================================================================
# DATA STRUCTURE TESTS
# ============================================================================

class TestDataStructures:
    """Tests for data structure classes."""

    def test_gitlab_config_from_environment(self):
        """Test GitLabConfig creation from environment variables."""
        with patch.dict('os.environ', {
            'CI_PROJECT_ID': '12345',
            'CI_MERGE_REQUEST_IID': '678',
            'CI_API_V4_URL': 'https://gitlab.example.com/api/v4',
            'GITLAB_API_TOKEN': 'secret-token',
            'CI_MERGE_REQUEST_DIFF_BASE_SHA': 'abc123',
        }):
            config = GitLabConfig.from_environment()
            assert config.project_id == '12345'
            assert config.mr_iid == '678'
            assert config.api_url == 'https://gitlab.example.com/api/v4'
            assert config.api_token == 'secret-token'
            assert config.base_sha == 'abc123'

    def test_gitlab_config_defaults(self):
        """Test GitLabConfig with default values."""
        with patch.dict('os.environ', {}, clear=True):
            config = GitLabConfig.from_environment()
            assert config.project_id is None
            assert config.mr_iid is None
            assert config.base_sha == 'main'  # Default value

    def test_gitlab_config_lint_base_branch(self):
        """Test GitLabConfig with LINT_BASE_BRANCH for local testing."""
        with patch.dict('os.environ', {
            'LINT_BASE_BRANCH': 'develop',
        }, clear=True):
            config = GitLabConfig.from_environment()
            assert config.base_sha == 'develop'

    def test_gitlab_config_priority_ci_over_lint_base_branch(self):
        """Test that CI_MERGE_REQUEST_DIFF_BASE_SHA takes priority over LINT_BASE_BRANCH."""
        with patch.dict('os.environ', {
            'CI_MERGE_REQUEST_DIFF_BASE_SHA': 'abc123',
            'LINT_BASE_BRANCH': 'develop',
        }, clear=True):
            config = GitLabConfig.from_environment()
            # CI variable should take priority
            assert config.base_sha == 'abc123'

    def test_gitlab_config_lint_base_branch_fallback(self):
        """Test that LINT_BASE_BRANCH is used when CI variable is not set."""
        with patch.dict('os.environ', {
            'LINT_BASE_BRANCH': 'release/v1.0',
        }, clear=True):
            config = GitLabConfig.from_environment()
            assert config.base_sha == 'release/v1.0'

    def test_validation_result_ok(self):
        """Test ValidationResult.ok() factory method."""
        result = ValidationResult.ok()
        assert result.success is True
        assert result.error_message is None

    def test_validation_result_fail(self):
        """Test ValidationResult.fail() factory method."""
        result = ValidationResult.fail("Error occurred")
        assert result.success is False
        assert result.error_message == "Error occurred"


# ============================================================================
# FILE OPERATIONS TESTS
# ============================================================================

class TestFileOperations:
    """Tests for file operation functions."""

    def test_read_linterignore_file(self, tmp_path):
        """Test reading linterignore file."""
        # Create temporary linterignore file
        linterignore = tmp_path / "linterignore"
        linterignore.write_text("file1.txt\ndir1/*\n\nfile2.py\n")

        result = read_linterignore_file(linterignore)
        assert result == ["file1.txt", "dir1/*", "file2.py"]

    def test_expand_directory_patterns_without_wildcards(self):
        """Test pattern expansion without directory wildcards."""
        patterns = ["file1.txt", "file2.py"]
        result = expand_directory_patterns(patterns)
        assert result == {"file1.txt", "file2.py"}

    def test_expand_directory_patterns_with_wildcards(self, tmp_path):
        """Test pattern expansion with directory wildcards."""
        # Create test directory structure
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        (test_dir / "file1.txt").touch()
        (test_dir / "file2.py").touch()

        # Change to tmp_path for relative path testing
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = ["testdir/*", "other.txt"]
            result = expand_directory_patterns(patterns)

            # Check that directory files are included
            assert "testdir/*" in result
            assert "other.txt" in result
            # Actual files should be added
            assert any("file1.txt" in str(f) for f in result)
            assert any("file2.py" in str(f) for f in result)
        finally:
            os.chdir(original_cwd)


# ============================================================================
# NEWLINE AT EOF VALIDATION TESTS
# ============================================================================

class TestNewlineAtEOF:
    """Tests for newline-at-EOF validation."""

    def test_is_binary_file_with_binary(self, tmp_path):
        """Test binary file detection with actual binary content."""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        assert is_binary_file(str(binary_file)) is True

    def test_is_binary_file_with_text(self, tmp_path):
        """Test binary file detection with text content."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is plain text\n")
        assert is_binary_file(str(text_file)) is False

    def test_is_binary_file_with_nonexistent(self):
        """Test binary file detection with nonexistent file."""
        assert is_binary_file("/nonexistent/file.txt") is True

    def test_should_skip_newline_check_nonexistent(self):
        """Test that non-existent files are skipped."""
        assert should_skip_newline_check("/nonexistent/file.txt") is True

    def test_should_skip_newline_check_directory(self, tmp_path):
        """Test that directories are skipped."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        assert should_skip_newline_check(str(test_dir)) is True

    def test_should_skip_newline_check_symlink(self, tmp_path):
        """Test that symlinks are skipped."""
        real_file = tmp_path / "real.txt"
        real_file.write_text("content\n")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)
        assert should_skip_newline_check(str(symlink)) is True

    def test_should_skip_newline_check_binary(self, tmp_path):
        """Test that binary files are skipped."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        assert should_skip_newline_check(str(binary_file)) is True

    def test_should_skip_newline_check_text_file(self, tmp_path):
        """Test that regular text files are NOT skipped."""
        text_file = tmp_path / "text.txt"
        text_file.write_text("regular text file\n")
        assert should_skip_newline_check(str(text_file)) is False

    @pytest.mark.parametrize("filename", [
        "image.svg",
        "changes.patch",
        "changes.diff",
        "server.pem",
        "server.crt",
        "id_rsa.pub",
        "id_rsa.key",
        "uv.lock",
        "poetry.lock",
        "package-lock.json.lock",
        "IMAGE.SVG",   # case-insensitive
        "CERT.PEM",    # case-insensitive
    ])
    def test_should_skip_newline_check_tool_generated_extension(self, tmp_path, filename):
        """Test that tool-generated file extensions are skipped."""
        f = tmp_path / filename
        f.write_text("content without newline")
        assert should_skip_newline_check(str(f)) is True

    @pytest.mark.parametrize("filename", [
        "RPM-GPG-KEY-redhat",
        "RPM-GPG-KEY-epel-9",
        "RPM-GPG-KEY-",
    ])
    def test_should_skip_newline_check_gpg_key_filename(self, tmp_path, filename):
        """Test that RPM-GPG-KEY-* files are skipped regardless of extension."""
        f = tmp_path / filename
        f.write_text("-----BEGIN PGP PUBLIC KEY BLOCK-----\n")
        assert should_skip_newline_check(str(f)) is True

    def test_should_skip_newline_check_python_not_skipped(self, tmp_path):
        """Test that .py files are NOT skipped by the tool-generated logic."""
        py_file = tmp_path / "script.py"
        py_file.write_text("print('hello')")  # no trailing newline
        assert should_skip_newline_check(str(py_file)) is False

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_tool_generated(self, mock_get_files, tmp_path):
        """Test that tool-generated files missing newlines do not cause failures."""
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(b"<svg></svg>")  # no trailing newline
        patch_file = tmp_path / "fix.patch"
        patch_file.write_bytes(b"--- a/foo\n+++ b/foo")  # no trailing newline
        gpg_key = tmp_path / "RPM-GPG-KEY-redhat"
        gpg_key.write_bytes(b"-----BEGIN PGP PUBLIC KEY BLOCK-----")

        mock_get_files.return_value = [str(svg_file), str(patch_file), str(gpg_key)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_py_still_checked(self, mock_get_files, tmp_path):
        """Test that .py files are still checked even when tool-generated files are present."""
        py_file = tmp_path / "script.py"
        py_file.write_bytes(b"print('hello')")  # no trailing newline
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(b"<svg></svg>")  # no trailing newline — should be ignored

        mock_get_files.return_value = [str(py_file), str(svg_file)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        assert str(py_file) in result.error_message
        assert str(svg_file) not in result.error_message

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_success(self, mock_get_files, tmp_path):
        """Test validation when all text files have newlines at EOF."""
        # Create test files with newlines
        file1 = tmp_path / "file1.txt"
        file1.write_text("content\n")
        file2 = tmp_path / "file2.py"
        file2.write_text("#!/usr/bin/env python3\nprint('hello')\n")

        mock_get_files.return_value = [str(file1), str(file2)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True
        assert result.error_message is None

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_missing_newline(self, mock_get_files, tmp_path):
        """Test validation when files are missing newlines at EOF."""
        # Create files without newlines
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content without newline")
        file2 = tmp_path / "file2.py"
        file2.write_bytes(b"print('hello')")

        mock_get_files.return_value = [str(file1), str(file2)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        assert "do not end with a newline" in result.error_message
        assert str(file1) in result.error_message
        assert str(file2) in result.error_message

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_empty_file(self, mock_get_files, tmp_path):
        """Test validation with empty file (should pass)."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        mock_get_files.return_value = [str(empty_file)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_binary(self, mock_get_files, tmp_path):
        """Test that binary files are skipped."""
        # Create binary file without newline
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00')

        mock_get_files.return_value = [str(binary_file)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True  # Binary files are skipped

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_symlinks(self, mock_get_files, tmp_path):
        """Test that symlinks are skipped."""
        # Create a real file and a symlink to it
        real_file = tmp_path / "real.txt"
        real_file.write_bytes(b"content without newline")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        # Only check the symlink, not the real file
        mock_get_files.return_value = [str(symlink)]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True  # Symlinks are skipped

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_deleted(self, mock_get_files):
        """Test that deleted files (non-existent) are skipped."""
        mock_get_files.return_value = ["/nonexistent/deleted.txt"]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is True  # Deleted files are skipped

    @patch('scripts.mr_commit_linter.get_commit_modified_files')
    def test_validate_files_newline_at_eof_mixed_files(self, mock_get_files, tmp_path):
        """Test validation with mix of valid, invalid, and skipped files."""
        # File with newline (valid)
        good_file = tmp_path / "good.txt"
        good_file.write_text("content\n")

        # File without newline (invalid)
        bad_file = tmp_path / "bad.txt"
        bad_file.write_bytes(b"no newline")

        # Binary file (skip)
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02')

        # Symlink (skip)
        real_file = tmp_path / "real.txt"
        real_file.write_text("content\n")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        mock_get_files.return_value = [
            str(good_file),
            str(bad_file),
            str(binary_file),
            str(symlink),
        ]

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        # Only bad_file should be in the error
        assert str(bad_file) in result.error_message
        # Others should not be mentioned
        assert str(good_file) not in result.error_message or "do not end" not in result.error_message
        assert str(binary_file) not in result.error_message
        assert str(symlink) not in result.error_message


# ============================================================================
# GITLAB API TESTS
# ============================================================================

class TestGitLabAPI:
    """Tests for GitLab API functions."""

    @patch('scripts.mr_commit_linter.requests.get')
    def test_get_mr_commits_from_api_success(self, mock_get):
        """Test fetching MR commits from GitLab API successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "abc123", "title": "RHELAI-1234: Third commit"},
            {"id": "def456", "title": "RHELAI-1235: Second commit"},
            {"id": "ghi789", "title": "RHELAI-1236: First commit"},
        ]
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )

        result = get_mr_commits_from_api(config)

        # Should return commits in reverse order (oldest first)
        assert result == ["ghi789", "def456", "abc123"]
        mock_get.assert_called_once_with(
            "https://gitlab.example.com/api/v4/projects/12345/merge_requests/678/commits",
            headers={"PRIVATE-TOKEN": "secret-token"},
            timeout=10
        )

    @patch('scripts.mr_commit_linter.requests.get')
    def test_get_mr_commits_from_api_failure(self, mock_get):
        """Test handling of API request failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )

        result = get_mr_commits_from_api(config)
        assert result is None

    @patch('scripts.mr_commit_linter.requests.get')
    def test_get_mr_commits_from_api_network_error(self, mock_get):
        """Test handling of network errors."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection timeout")

        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )

        result = get_mr_commits_from_api(config)
        assert result is None

    def test_get_mr_commits_from_api_missing_config(self):
        """Test that function returns None when config is incomplete."""
        # Missing MR IID
        config = GitLabConfig(
            project_id="12345",
            mr_iid=None,
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None

        # Missing API token
        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token=None,
            base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None


class TestValidateAllCommits:
    """Tests for validate_all_commits function."""

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch('scripts.mr_commit_linter.validate_commit')
    @patch('scripts.mr_commit_linter.run_git_command')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_validate_all_commits_uses_api(self, mock_git, mock_validate, mock_get_info, mock_api):
        """Test that validate_all_commits uses GitLab API when available."""
        # Mock API returning commit SHAs
        mock_api.return_value = ["abc123", "def456"]

        # Mock git command for displaying commit info
        mock_git.return_value = (True, "abc123 RHELAI-1234: Commit 1")

        # Mock commit info
        mock_get_info.return_value = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        # Mock validation returning no errors
        mock_validate.return_value = []

        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )

        errors = validate_all_commits(config)

        # Should use API
        mock_api.assert_called_once_with(config)
        assert errors == []

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commits_in_range')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch('scripts.mr_commit_linter.validate_commit')
    @patch('scripts.mr_commit_linter.run_git_command')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_validate_all_commits_fallback_to_git_log(self, mock_git, mock_validate,
                                                       mock_get_info, mock_get_range, mock_api):
        """Test that validate_all_commits falls back to git log when API unavailable."""
        # Mock API returning None (unavailable)
        mock_api.return_value = None

        # Mock git log returning commits
        mock_get_range.return_value = [
            "abc123 RHELAI-1234: Commit 1",
            "def456 RHELAI-1235: Commit 2"
        ]

        # Mock git command for displaying commit info
        mock_git.return_value = (True, "abc123 RHELAI-1234: Commit 1")

        # Mock commit info
        mock_get_info.return_value = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )

        # Mock validation returning no errors
        mock_validate.return_value = []

        config = GitLabConfig(
            project_id=None,
            mr_iid=None,
            api_url=None,
            api_token=None,
            base_sha="main"
        )

        errors = validate_all_commits(config)

        # Should fallback to git log
        mock_api.assert_called_once_with(config)
        mock_get_range.assert_called_once_with("main")
        assert errors == []

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_validate_all_commits_no_commits(self, mock_api):
        """Test validate_all_commits when there are no commits."""
        # Mock API returning empty list
        mock_api.return_value = []

        config = GitLabConfig(
            project_id="12345",
            mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token",
            base_sha="main"
        )

        errors = validate_all_commits(config)
        assert errors == []



# ============================================================================
# CLOSING PHRASE PATTERN TESTS
# ============================================================================

class TestClosingPhrasePattern:
    """Tests for the closing keyword + Jira ID regex patterns."""

    # --- Patterns that SHOULD match ---

    @pytest.mark.parametrize("text,expected_ids", [
        ("Closes AIPCC-100", ["AIPCC-100"]),
        ("closes AIPCC-100", ["AIPCC-100"]),
        ("Close AIPCC-100", ["AIPCC-100"]),
        ("Closed AIPCC-100", ["AIPCC-100"]),
        ("Closing AIPCC-100", ["AIPCC-100"]),
        ("Fixes AIPCC-100", ["AIPCC-100"]),
        ("Fix AIPCC-100", ["AIPCC-100"]),
        ("Fixed AIPCC-100", ["AIPCC-100"]),
        ("Fixing AIPCC-100", ["AIPCC-100"]),
        ("Resolves AIPCC-100", ["AIPCC-100"]),
        ("Resolve AIPCC-100", ["AIPCC-100"]),
        ("Resolved AIPCC-100", ["AIPCC-100"]),
        ("Resolving AIPCC-100", ["AIPCC-100"]),
        ("Implements AIPCC-100", ["AIPCC-100"]),
        ("Implement AIPCC-100", ["AIPCC-100"]),
        ("Implemented AIPCC-100", ["AIPCC-100"]),
        ("Implementing AIPCC-100", ["AIPCC-100"]),
    ])
    def test_all_keyword_conjugations(self, text, expected_ids):
        """Test all closing keyword conjugations match."""
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == expected_ids

    def test_optional_colon_after_keyword(self):
        """Test that optional colon after keyword is supported."""
        matches = CLOSING_PHRASE_PATTERN.findall("Fixes: AIPCC-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert ids[0].upper() == "AIPCC-100"

    def test_comma_separated_ids(self):
        """Test comma-separated Jira IDs after closing keyword."""
        matches = CLOSING_PHRASE_PATTERN.findall("Closes AIPCC-100, AIPCC-101")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101"]

    def test_and_separated_ids(self):
        """Test 'and'-separated Jira IDs after closing keyword."""
        matches = CLOSING_PHRASE_PATTERN.findall("Resolves AIPCC-100 and AIPCC-101")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101"]

    def test_comma_and_separated_ids(self):
        """Test comma+and separated Jira IDs."""
        matches = CLOSING_PHRASE_PATTERN.findall(
            "Fixed: AIPCC-100, AIPCC-101 and AIPCC-102"
        )
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101", "AIPCC-102"]

    def test_case_insensitive_keyword(self):
        """Test that keywords are matched case-insensitively."""
        for text in ["FIXES AIPCC-100", "fixes AIPCC-100", "Fixes AIPCC-100"]:
            matches = CLOSING_PHRASE_PATTERN.findall(text)
            assert len(matches) == 1, f"Failed for: {text}"

    def test_multiple_spaces_between_keyword_and_id(self):
        """Test multiple spaces between keyword and Jira ID."""
        matches = CLOSING_PHRASE_PATTERN.findall("Fixes   AIPCC-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert ids[0].upper() == "AIPCC-100"

    def test_various_project_keys(self):
        """Test different Jira project key formats."""
        for key in ["RHELAI-1234", "RHOAIENG-5678", "AB-1", "PROJ_KEY-99"]:
            matches = CLOSING_PHRASE_PATTERN.findall(f"Fixes {key}")
            assert len(matches) == 1, f"Failed for key: {key}"

    def test_tab_separator_no_match(self):
        """Test that tab between keyword and Jira ID does NOT match."""
        matches = CLOSING_PHRASE_PATTERN.findall("Closes\tAIPCC-100")
        assert len(matches) == 0

    def test_colon_without_space_no_match(self):
        """Test that colon without trailing space does NOT match."""
        matches = CLOSING_PHRASE_PATTERN.findall("Closes:AIPCC-100")
        assert len(matches) == 0

    def test_three_id_comma_list(self):
        """Test three comma-separated Jira IDs."""
        matches = CLOSING_PHRASE_PATTERN.findall("Closes AIPCC-100, AIPCC-101, AIPCC-102")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101", "AIPCC-102"]

    def test_multiple_closing_phrases_in_text(self):
        """Test multiple closing phrases found via finditer."""
        text = "Closes AIPCC-100. Also fixes AIPCC-200"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 2
        assert JIRA_ID_EXTRACT_PATTERN.findall(matches[0]) == ["AIPCC-100"]
        assert JIRA_ID_EXTRACT_PATTERN.findall(matches[1]) == ["AIPCC-200"]

    def test_lowercase_jira_id_matches(self):
        """Test that lowercase Jira ID matches due to re.IGNORECASE."""
        matches = CLOSING_PHRASE_PATTERN.findall("fixes aipcc-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100"]

    def test_keyword_substring_unresolved_no_match(self):
        """Test that 'unresolved' (contains 'resolve') does NOT match."""
        matches = CLOSING_PHRASE_PATTERN.findall("unresolved AIPCC-100")
        assert len(matches) == 0

    # --- Patterns that should NOT match ---

    def test_no_match_bare_jira_id(self):
        """Test that bare Jira ID without closing keyword does not match."""
        matches = CLOSING_PHRASE_PATTERN.findall("AIPCC-100: Fix the bug")
        assert len(matches) == 0

    def test_no_match_jira_id_before_keyword(self):
        """Test standard commit format (ID before keyword) does not match."""
        matches = CLOSING_PHRASE_PATTERN.findall("AIPCC-100: Fix authentication bug")
        assert len(matches) == 0

    def test_no_match_related_to(self):
        """Test 'Related to' does not match as a closing keyword."""
        matches = CLOSING_PHRASE_PATTERN.findall("Related to AIPCC-100")
        assert len(matches) == 0

    def test_no_match_see_also(self):
        """Test 'See also' does not match."""
        matches = CLOSING_PHRASE_PATTERN.findall("See also AIPCC-100")
        assert len(matches) == 0

    def test_no_match_ref(self):
        """Test 'Ref' does not match."""
        matches = CLOSING_PHRASE_PATTERN.findall("Ref AIPCC-100")
        assert len(matches) == 0

    def test_no_cross_newline_match(self):
        """Test that keyword and Jira ID separated by newline do NOT match."""
        # This is the critical false-positive case from the consultation
        text = "Ready to close\nAIPCC-100: Add feature"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 0

    def test_no_cross_newline_match_fix(self):
        """Test cross-newline with 'fix' keyword does not match."""
        text = "We need to fix\nAIPCC-100: Update config"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 0

    def test_keyword_in_middle_of_word_no_match(self):
        """Test that keyword embedded in another word does not match."""
        # 'prefix' contains 'fix' but \b prevents matching
        matches = CLOSING_PHRASE_PATTERN.findall("prefix AIPCC-100")
        assert len(matches) == 0


# ============================================================================
# JIRA CONFIG TESTS
# ============================================================================

class TestJiraConfig:
    """Tests for JiraConfig dataclass."""

    def test_from_environment_with_all_vars(self):
        """Test JiraConfig creation with all environment variables set."""
        with patch.dict('os.environ', {
            'JIRA_URL': 'https://jira.example.com',
            'JIRA_USERNAME': 'user@example.com',
            'JIRA_API_TOKEN': 'secret-token',
        }):
            config = JiraConfig.from_environment()
            assert config.site_url == 'https://jira.example.com'
            assert config.username == 'user@example.com'
            assert config.api_token == 'secret-token'
            assert config.is_configured is True

    def test_from_environment_default_url(self):
        """Test JiraConfig uses default URL when JIRA_URL is not set."""
        with patch.dict('os.environ', {
            'JIRA_USERNAME': 'user@example.com',
            'JIRA_API_TOKEN': 'secret-token',
        }, clear=True):
            config = JiraConfig.from_environment()
            assert config.site_url == 'https://redhat.atlassian.net'
            assert config.is_configured is True

    def test_from_environment_strips_trailing_slash(self):
        """Test that trailing slash is stripped from JIRA_URL."""
        with patch.dict('os.environ', {
            'JIRA_URL': 'https://jira.example.com/',
            'JIRA_USERNAME': 'user@example.com',
            'JIRA_API_TOKEN': 'secret-token',
        }):
            config = JiraConfig.from_environment()
            assert config.site_url == 'https://jira.example.com'

    def test_not_configured_missing_username(self):
        """Test is_configured is False when username is missing."""
        config = JiraConfig(
            site_url='https://jira.example.com',
            username=None,
            api_token='token',
        )
        assert config.is_configured is False

    def test_not_configured_missing_token(self):
        """Test is_configured is False when token is missing."""
        config = JiraConfig(
            site_url='https://jira.example.com',
            username='user',
            api_token=None,
        )
        assert config.is_configured is False

    def test_not_configured_missing_both(self):
        """Test is_configured is False when both credentials are missing."""
        with patch.dict('os.environ', {}, clear=True):
            config = JiraConfig.from_environment()
            assert config.is_configured is False



# ============================================================================
# JIRA API TESTS
# ============================================================================

class TestGetJiraIssueType:
    """Tests for get_jira_issue_type function."""

    def _make_config(self):
        return JiraConfig(
            site_url='https://jira.example.com',
            username='user@example.com',
            api_token='secret-token',
        )

    @patch('scripts.mr_commit_linter.requests.get')
    def test_returns_issue_type(self, mock_get):
        """Test successful issue type retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'fields': {'issuetype': {'name': 'Epic'}}
        }
        mock_get.return_value = mock_response

        config = self._make_config()
        result = get_jira_issue_type('AIPCC-100', config)
        assert result == 'Epic'

        mock_get.assert_called_once_with(
            'https://jira.example.com/rest/api/2/issue/AIPCC-100?fields=issuetype',
            auth=('user@example.com', 'secret-token'),
            timeout=10,
        )

    @patch('scripts.mr_commit_linter.requests.get')
    def test_returns_story_type(self, mock_get):
        """Test retrieval of non-Epic issue type."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'fields': {'issuetype': {'name': 'Story'}}
        }
        mock_get.return_value = mock_response

        config = self._make_config()
        result = get_jira_issue_type('AIPCC-200', config)
        assert result == 'Story'

    @patch('scripts.mr_commit_linter.requests.get')
    def test_api_error_returns_none(self, mock_get):
        """Test that API errors return None."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = self._make_config()
        result = get_jira_issue_type('AIPCC-999', config)
        assert result is None

    @patch('scripts.mr_commit_linter.requests.get')
    def test_network_error_returns_none(self, mock_get):
        """Test that network errors return None."""
        mock_get.side_effect = requests_lib.RequestException("Connection timeout")

        config = self._make_config()
        result = get_jira_issue_type('AIPCC-100', config)
        assert result is None

    @patch('scripts.mr_commit_linter.requests.get')
    def test_auth_error_returns_none(self, mock_get):
        """Test that authentication errors return None."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        config = self._make_config()
        result = get_jira_issue_type('AIPCC-100', config)
        assert result is None


# ============================================================================
# PROTECTED TYPE CLOSURE VALIDATION TESTS
# ============================================================================

class TestValidateNoProtectedTypeClosure:
    """Tests for validate_no_protected_type_closure function."""

    def _make_gitlab_config(self):
        return GitLabConfig(
            project_id='12345',
            mr_iid='678',
            api_url='https://gitlab.example.com/api/v4',
            api_token='gitlab-token',
            base_sha='main',
        )

    def _make_jira_config(self):
        return JiraConfig(
            site_url='https://jira.example.com',
            username='user@example.com',
            api_token='jira-token',
        )

    def _mock_jira_type(self, mock_get, type_map):
        """Helper to mock Jira API responses for multiple issue keys."""
        def side_effect(url, **kwargs):
            resp = Mock()
            for key, issue_type in type_map.items():
                # Match full issue key in URL path to avoid
                # substring collisions (AIPCC-10 matching AIPCC-100)
                if f"/issue/{key}?" in url:
                    resp.status_code = 200
                    resp.json.return_value = {
                        'fields': {'issuetype': {'name': issue_type}}
                    }
                    return resp
            resp.status_code = 404
            return resp
        mock_get.side_effect = side_effect

    # --- Detection tests ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100\n\nSigned-off-by: Dev',
    })
    def test_epic_in_mr_description(self, mock_commits, mock_get):
        """Test detection of closing keyword + Epic ID in MR description."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'AIPCC-100' in errors[0]
        assert 'Epic' in errors[0]
        assert 'MR description' in errors[0]

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'Closes AIPCC-100',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description\n\nSigned-off-by: Dev',
    })
    def test_epic_in_mr_title(self, mock_commits, mock_get):
        """Test detection of closing keyword + Epic ID in MR title."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'MR title' in errors[0]

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description\n\nSigned-off-by: Dev',
    })
    def test_epic_in_commit_message(self, mock_info, mock_commits, mock_get):
        """Test detection of closing keyword + Epic ID in commit message."""
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123',
            title='AIPCC-999: Add feature',
            body='Resolves AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'commit message' in errors[0]

    # --- Non-detection tests (should pass) ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-100: Fix the bug',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Related to AIPCC-100\n\nSigned-off-by: Dev',
    })
    def test_bare_epic_id_passes(self, mock_commits, mock_get):
        """Test that bare Epic ID without closing keyword passes."""
        mock_commits.return_value = []
        # Jira API should NOT be called since no closing pattern is found
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-200\n\nSigned-off-by: Dev',
    })
    def test_non_epic_with_closing_keyword_passes(self, mock_commits, mock_get):
        """Test that non-Epic ticket with closing keyword passes."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-200': 'Story'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Closes AIPCC-200, AIPCC-100\n\nSigned-off-by: Dev',
    })
    def test_mixed_epic_and_non_epic(self, mock_commits, mock_get):
        """Test comma-separated IDs where one is Epic and one is not."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {
            'AIPCC-200': 'Story',
            'AIPCC-100': 'Epic',
        })

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        # Only the Epic should cause an error
        assert len(errors) == 1
        assert 'AIPCC-100' in errors[0]

    # --- Project key filtering ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes RHELAI-500\n\nSigned-off-by: Dev',
    })
    def test_non_aipcc_ticket_skipped(self, mock_commits, mock_get):
        """Test that non-AIPCC tickets are not checked even with closing keyword."""
        mock_commits.return_value = []
        # Jira API should NOT be called for non-AIPCC tickets
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    # --- Cross-boundary safety ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'We need to close',
    })
    def test_no_cross_boundary_false_positive(self, mock_info, mock_commits, mock_get):
        """Test that keyword at end of description + ID at start of commit
        does NOT produce a false positive."""
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123',
            title='AIPCC-100: Update config',
            body='Signed-off-by: Dev',
        )

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    # --- Skip conditions ---

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
        'CI_MERGE_REQUEST_LABELS': 'bug, skip-issue-type-check, urgent',
    })
    def test_skip_with_label(self, mock_commits):
        """Test that skip-issue-type-check label is detected among multiple labels."""
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_commits.assert_not_called()  # Should not even fetch commits

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
        'CI_MERGE_REQUEST_LABELS': 'skip-issue-type-check',
    })
    def test_skip_with_label_alone(self, mock_commits):
        """Test skip-issue-type-check label when it is the only label (no comma splitting)."""
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_skip_with_missing_jira_credentials(self, mock_commits):
        """Test that missing Jira credentials skip the check."""
        jira_config = JiraConfig(
            site_url='https://jira.example.com',
            username=None,
            api_token=None,
        )
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), jira_config
        )
        assert len(errors) == 0

    @patch.dict('os.environ', {}, clear=True)
    def test_skip_when_running_locally(self):
        """Test that the check is skipped when not in an MR pipeline."""
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    # --- API failure handling ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_api_failure_skips_check_for_that_id(self, mock_commits, mock_get):
        """Test that Jira API failure skips the check for that ID."""
        mock_commits.return_value = []
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0  # API failure -> skip, not error

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_network_failure_skips_check(self, mock_commits, mock_get):
        """Test that network failure skips the check."""
        mock_commits.return_value = []
        mock_get.side_effect = requests_lib.RequestException("timeout")

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    # --- Optional colon variant ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes: AIPCC-100\n\nSigned-off-by: Dev',
    })
    def test_colon_variant_detects_epic(self, mock_commits, mock_get):
        """Test that 'Fixes: AIPCC-100' variant detects Epic."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1

    # --- Commit fallback to git log ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commits_in_range')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description',
    })
    def test_fallback_to_git_log(self, mock_info, mock_range, mock_commits, mock_get):
        """Test fallback to git log when GitLab API is unavailable."""
        mock_commits.return_value = None  # API unavailable
        mock_range.return_value = ['abc123 AIPCC-999: Add feature']
        mock_info.return_value = CommitInfo(
            commit_id='abc123',
            title='AIPCC-999: Add feature',
            body='Implements AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        mock_range.assert_called_once()

    # --- Error message content ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_error_message_content(self, mock_commits, mock_get):
        """Test that error message contains helpful information."""
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'AIPCC-100' in errors[0]
        assert 'Epic' in errors[0]
        assert 'auto-transition' in errors[0]
        assert 'skip-issue-type-check' in errors[0]
        assert 'Related to' in errors[0] or 'Ref' in errors[0]

    # --- INTERNAL commit handling ---

    @patch('scripts.mr_commit_linter.requests.get')
    @patch('scripts.mr_commit_linter.get_mr_commits_from_api')
    @patch('scripts.mr_commit_linter.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'INTERNAL: Update docs',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description\n\nSigned-off-by: Dev',
    })
    def test_internal_commit_still_checked(self, mock_info, mock_commits, mock_get):
        """Test that INTERNAL commits are still scanned for epic closure."""
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123',
            title='INTERNAL: Update docs',
            body='Closes AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})

        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for combined functionality."""

    def test_full_commit_validation_success(self):
        """Test complete commit validation with valid commit."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Implement new feature",
            body="This commit implements a new feature.\n\n"
                 "It includes comprehensive tests.\n\n"
                 "Signed-off-by: John Doe <john@example.com>"
        )

        # All validations should pass
        assert validate_commit_title(commit).success is True
        assert validate_commit_signed_off_by(commit).success is True

    def test_full_commit_validation_failure(self):
        """Test complete commit validation with invalid commit."""
        commit = CommitInfo(
            commit_id="abc123",
            title="Implement feature",  # No Jira ticket
            body="Short"  # Too short, no SOB
        )

        # Multiple validations should fail
        assert validate_commit_title(commit).success is False
        assert validate_commit_signed_off_by(commit).success is False

    def test_full_mr_validation_success(self):
        """Test complete MR validation with valid MR."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="RHELAI-1234: Feature implementation",
            description="This MR implements feature X.\n\n"
                       "Signed-off-by: John Doe <john@example.com>",
            author="developer"
        )

        assert validate_mr_title(mr_info).success is True
        assert validate_mr_description(mr_info).success is True


# ============================================================================
# MOCKING EXAMPLES FOR GIT COMMANDS
# ============================================================================

class TestGitCommandMocking:
    """Examples of how to test functions that call git commands."""

    @patch('scripts.mr_commit_linter.run_git_command')
    def test_get_commits_in_range_mock(self, mock_git):
        """Example: Mock git command to test get_commits_in_range."""
        mock_git.return_value = (True, "abc123 RHELAI-1234: Fix\ndef456 RHELAI-5678: Update\n")

    @patch('scripts.mr_commit_linter.requests.get')
    def test_get_mr_author_mock(self, mock_get):
        """Example: Mock API call to test get_mr_author."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "author": {"username": "developer"}
        }
        mock_get.return_value = mock_response


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    # Run with: python test_mr_commit_linter.py
    # Or better: pytest test_mr_commit_linter.py -v
    pytest.main([__file__, "-v"])
