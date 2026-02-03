#!/usr/bin/env python3
"""
Unit tests for mr_commit_linter.py

Run with: pytest tests/
"""

import pytest
from unittest.mock import Mock, patch

from scripts.mr_commit_linter import (
    CommitInfo,
    MergeRequestInfo,
    GitLabConfig,
    ValidationResult,
    contains_signed_off_by,
    has_jira_ticket,
    has_internal_keyword,
    validate_commit_title,
    validate_commit_signed_off_by,
    validate_commit_body_length,
    validate_mr_title,
    validate_mr_description,
    read_linterignore_file,
    expand_directory_patterns,
    MIN_COMMIT_BODY_LINES,
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
        """Test commit title validation with invalid title."""
        commit = CommitInfo(
            commit_id="abc123",
            title="Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must begin with a valid Jira ticket" in result.error_message
        assert result.error_message is not None

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

    def test_validate_commit_body_length_sufficient(self):
        """Test body length validation with sufficient lines."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Description line\n\nAnother line\nSigned-off-by: Dev"
        )
        result = validate_commit_body_length(commit)
        assert result.success is True

    def test_validate_commit_body_length_too_short(self):
        """Test body length validation with insufficient lines."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Short\n"
        )
        result = validate_commit_body_length(commit)
        assert result.success is False
        assert f"at least {MIN_COMMIT_BODY_LINES} lines" in result.error_message


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
        """Test MR title validation with invalid title."""
        mr_info = MergeRequestInfo(
            iid="123",
            title="Feature implementation",
            description="Description\n\nSigned-off-by: Dev",
            author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must begin with a valid Jira ticket" in result.error_message

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
        assert validate_commit_body_length(commit).success is True

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
        assert validate_commit_body_length(commit).success is False

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
