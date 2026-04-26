"""Tests for validators.commit module.

Ported from TestCommitValidation, validate_commit tests from TestMergeCommit,
and commit-related TestIntegration methods from test_mr_commit_linter.py.
"""

import pytest
from unittest.mock import patch

from config import ALLOWED_EMAIL_DOMAINS, CommitInfo
from validators.commit import (
    extract_sob_emails,
    is_valid_email_domain,
    validate_commit_email,
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


class TestEmailValidation:
    """Tests for email domain validation in commits."""

    @pytest.mark.parametrize("text,expected", [
        # Single SOB with email
        ("Description\n\nSigned-off-by: John Doe <john@redhat.com>", ["john@redhat.com"]),
        # Multiple SOB lines
        (
            "Description\n\nSigned-off-by: Alice <alice@redhat.com>\n"
            "Signed-off-by: Bob <bob@redhat.com>",
            ["alice@redhat.com", "bob@redhat.com"],
        ),
        # SOB without angle brackets — no email extractable
        ("Description\n\nSigned-off-by: John Doe", []),
        # Case-insensitive tag matching
        ("Description\n\nsigned-off-by: Jane <jane@redhat.com>", ["jane@redhat.com"]),
        ("Description\n\nSIGNED-OFF-BY: Jane <jane@redhat.com>", ["jane@redhat.com"]),
        # No SOB at all
        ("Just a plain description", []),
        # Mixed-case email — returned lowercase
        ("Signed-off-by: Dev <Dev.Name@RedHat.COM>", ["dev.name@redhat.com"]),
    ])
    def test_extract_sob_emails(self, text, expected):
        """Test email extraction from Signed-off-by lines."""
        assert extract_sob_emails(text) == expected

    @pytest.mark.parametrize("email,expected", [
        # Allowed domain
        ("user@redhat.com", True),
        # Case-insensitive domain
        ("user@RedHat.COM", True),
        # Subdomain rejected (exact match only)
        ("user@corp.redhat.com", False),
        # Machine hostname (subdomain of allowed domain)
        ("user@host01.subdomain.example.redhat.com", False),
        # Different organisation
        ("user@gmail.com", False),
        # No @ sign
        ("invalid-email", False),
        # Empty domain
        ("user@", False),
    ])
    def test_is_valid_email_domain(self, email, expected):
        """Test email domain validation against the allowlist."""
        assert is_valid_email_domain(email, ALLOWED_EMAIL_DOMAINS) == expected

    @patch('validators.files.get_commit_modified_files')
    @patch('validators.commit.should_skip_commit_validation')
    def test_validate_commit_email_valid(self, mock_skip, mock_files):
        """Test that commits with valid emails pass validation."""
        mock_skip.return_value = False
        mock_files.return_value = []

        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix authentication bug",
            body="Description of changes.\n\nSigned-off-by: Dev <dev@redhat.com>\n",
            author_email="dev@redhat.com",
        )
        errors = validate_commit(commit)
        assert not any("email" in e.lower() for e in errors)

    @pytest.mark.parametrize("author_email", [
        # Machine hostname (subdomain of allowed domain)
        "user@host01.subdomain.example.redhat.com",
        # Empty author email (git not configured)
        "",
    ])
    def test_validate_commit_email_invalid_author(self, author_email):
        """Test that commits with invalid author emails fail validation."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description.\n\nSigned-off-by: Dev <dev@redhat.com>\n",
            author_email=author_email,
        )
        result = validate_commit_email(commit)
        assert result.success is False

    def test_validate_commit_email_invalid_sob(self):
        """Test that commits with invalid Signed-off-by emails fail validation."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description.\n\nSigned-off-by: Dev <user@host01.subdomain.example.redhat.com>\n",
            author_email="dev@redhat.com",
        )
        result = validate_commit_email(commit)
        assert result.success is False
        assert "not in the allowed list" in result.error_message

    def test_validate_commit_email_malformed_sob(self):
        """Test that SOB tag without parseable <email> fails validation."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description.\n\nSigned-off-by: John Doe\n",
            author_email="dev@redhat.com",
        )
        result = validate_commit_email(commit)
        assert result.success is False
        assert "no email address" in result.error_message

    @pytest.mark.parametrize("enabled,should_pass", [
        (True, False),
        (False, True),
    ])
    def test_validate_commit_email_kill_switch(self, enabled, should_pass):
        """Test EMAIL_VALIDATION_ENABLED controls validation behaviour."""
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description.\n\nSigned-off-by: Dev <dev@redhat.com>\n",
            author_email="user@host01.subdomain.example.redhat.com",
        )
        with patch('validators.commit.EMAIL_VALIDATION_ENABLED', enabled):
            result = validate_commit_email(commit)
        assert result.success is should_pass


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
