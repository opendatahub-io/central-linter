"""Tests for validators.commit module.

Ported from TestCommitValidation, validate_commit tests from TestMergeCommit,
and commit-related TestIntegration methods from test_mr_commit_linter.py.
"""

from unittest.mock import patch

from config import CommitInfo
from validators.commit import (
    validate_commit_title,
    validate_commit_signed_off_by,
    validate_commit,
)


class TestCommitValidation:
    def test_validate_commit_title_with_jira(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix authentication bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True
        assert result.error_message is None

    def test_validate_commit_title_with_internal(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="INTERNAL: Update documentation",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True

    def test_validate_commit_title_invalid(self):
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
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234 Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must have a colon" in result.error_message

    def test_validate_commit_title_invalid_no_space_after_colon(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234:Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "exactly one space after colon" in result.error_message

    def test_validate_commit_title_revert_with_valid_inner_title(self):
        commit = CommitInfo(
            commit_id="abc123",
            title='Revert "AIPCC-1234: Fix authentication bug"',
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is True

    def test_validate_commit_title_revert_with_invalid_inner_title(self):
        commit = CommitInfo(
            commit_id="abc123",
            title='Revert "Fix authentication bug"',
            body="Description\n\nSigned-off-by: Dev"
        )
        result = validate_commit_title(commit)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_commit_signed_off_by_present(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Description of changes\n\nSigned-off-by: John Doe <john@example.com>"
        )
        result = validate_commit_signed_off_by(commit)
        assert result.success is True

    def test_validate_commit_signed_off_by_missing(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix",
            body="Description of changes"
        )
        result = validate_commit_signed_off_by(commit)
        assert result.success is False
        assert "does not contain a Signed-off-by" in result.error_message


class TestValidateCommit:
    @patch('validators.commit.should_skip_commit_validation')
    def test_skips_merge_commit(self, mock_should_skip):
        mock_should_skip.return_value = True
        commit = CommitInfo(
            commit_id="abc123",
            title="Merge branch 'feature' into 'main'",
            body="See merge request !123"
        )
        errors = validate_commit(commit)
        assert errors == []
        mock_should_skip.assert_called_once_with(commit)

    @patch('validators.files.get_commit_modified_files')
    @patch('validators.commit.should_skip_commit_validation')
    def test_validates_regular_commit(self, mock_should_skip, mock_get_files):
        mock_should_skip.return_value = False
        mock_get_files.return_value = []
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Short"
        )
        errors = validate_commit(commit)
        assert len(errors) > 0
        mock_should_skip.assert_called_once_with(commit)


class TestIntegrationCommit:
    def test_full_commit_validation_success(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Implement new feature",
            body="This commit implements a new feature.\n\n"
                 "It includes comprehensive tests.\n\n"
                 "Signed-off-by: John Doe <john@example.com>"
        )
        assert validate_commit_title(commit).success is True
        assert validate_commit_signed_off_by(commit).success is True

    def test_full_commit_validation_failure(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="Implement feature",
            body="Short"
        )
        assert validate_commit_title(commit).success is False
        assert validate_commit_signed_off_by(commit).success is False
