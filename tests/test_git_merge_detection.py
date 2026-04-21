"""Tests for git_utils.merge_detection module."""

from unittest.mock import patch

from config import CommitInfo
from git_utils.merge_detection import (
    is_merge_commit,
    get_cherry_pick_source,
    is_parent_merge_commit,
    should_skip_commit_validation,
)


class TestIsMergeCommit:
    @patch('git_utils.merge_detection.run_git_command')
    def test_true_with_two_parents(self, mock_git):
        mock_git.return_value = (True, "abc123 def456 ghi789\n")
        assert is_merge_commit("abc123") is True

    @patch('git_utils.merge_detection.run_git_command')
    def test_false_with_one_parent(self, mock_git):
        mock_git.return_value = (True, "abc123 def456\n")
        assert is_merge_commit("abc123") is False

    @patch('git_utils.merge_detection.run_git_command')
    def test_git_failure(self, mock_git):
        mock_git.return_value = (False, "error")
        assert is_merge_commit("abc123") is False


class TestGetCherryPickSource:
    def test_found(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\n(cherry picked from commit def456789)"
        )
        assert get_cherry_pick_source(commit) == "def456789"

    def test_not_found(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        assert get_cherry_pick_source(commit) is None


class TestIsParentMergeCommit:
    @patch('git_utils.merge_detection.is_merge_commit')
    def test_true_cherry_picked_merge(self, mock_is_merge):
        mock_is_merge.return_value = True
        commit = CommitInfo(
            commit_id="abc123",
            title="Merge branch 'feature' into 'main'",
            body="See merge request !123\n\n(cherry picked from commit def456789)"
        )
        assert is_parent_merge_commit(commit) is True
        mock_is_merge.assert_called_once_with("def456789")

    @patch('git_utils.merge_detection.is_merge_commit')
    def test_false_cherry_picked_regular(self, mock_is_merge):
        mock_is_merge.return_value = False
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev\n\n(cherry picked from commit def456789)"
        )
        assert is_parent_merge_commit(commit) is False
        mock_is_merge.assert_called_once_with("def456789")

    def test_not_cherry_picked(self):
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Description\n\nSigned-off-by: Dev"
        )
        assert is_parent_merge_commit(commit) is False


class TestShouldSkipCommitValidation:
    @patch('git_utils.merge_detection.is_merge_commit')
    def test_skips_merge_commit(self, mock_is_merge):
        mock_is_merge.return_value = True
        commit = CommitInfo(commit_id="abc123", title="Merge", body="")
        assert should_skip_commit_validation(commit) is True

    @patch('git_utils.merge_detection.is_parent_merge_commit')
    @patch('git_utils.merge_detection.is_merge_commit')
    def test_skips_cherry_picked_merge(self, mock_is_merge, mock_parent):
        mock_is_merge.return_value = False
        mock_parent.return_value = True
        commit = CommitInfo(
            commit_id="abc123",
            title="Merge",
            body="(cherry picked from commit def456)"
        )
        assert should_skip_commit_validation(commit) is True

    @patch('git_utils.merge_detection.is_parent_merge_commit')
    @patch('git_utils.merge_detection.is_merge_commit')
    def test_does_not_skip_regular(self, mock_is_merge, mock_parent):
        mock_is_merge.return_value = False
        mock_parent.return_value = False
        commit = CommitInfo(
            commit_id="abc123",
            title="RHELAI-1234: Fix bug",
            body="Signed-off-by: Dev"
        )
        assert should_skip_commit_validation(commit) is False
