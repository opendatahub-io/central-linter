"""Tests for git.commands module."""

import subprocess
from unittest.mock import patch, MagicMock

from config import CommitInfo
from git.commands import run_git_command, get_commits_in_range, get_commit_info, get_commit_modified_files


class TestRunGitCommand:
    @patch('git.commands.subprocess.run')
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output text", stderr="")
        success, output = run_git_command(["git", "status"])
        assert success is True
        assert output == "output text"

    @patch('git.commands.subprocess.run')
    def test_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error msg")
        success, output = run_git_command(["git", "bad-command"])
        assert success is False
        assert output == "error msg"


class TestGetCommitsInRange:
    @patch('git.commands.run_git_command')
    def test_returns_split_lines(self, mock_git):
        mock_git.return_value = (True, "abc123 First commit\ndef456 Second commit\n")
        result = get_commits_in_range("main")
        assert result == ["abc123 First commit", "def456 Second commit"]

    @patch('git.commands.run_git_command')
    def test_failure_exits(self, mock_git):
        mock_git.return_value = (False, "error")
        import pytest
        with pytest.raises(SystemExit):
            get_commits_in_range("main")


class TestGetCommitInfo:
    @patch('git.commands.run_git_command')
    def test_builds_commit_info(self, mock_git):
        mock_git.side_effect = [
            (True, "This is the body\n\nSigned-off-by: Dev"),
            (True, "  RHELAI-1234: Fix bug  \n"),
        ]
        result = get_commit_info("abc123")
        assert isinstance(result, CommitInfo)
        assert result.commit_id == "abc123"
        assert result.title == "RHELAI-1234: Fix bug"
        assert "Signed-off-by" in result.body


class TestGetCommitModifiedFiles:
    @patch('git.commands.run_git_command')
    def test_parses_numstat(self, mock_git):
        mock_git.return_value = (True, "\n1\t2\tfile1.py\n3\t4\tfile2.txt\n")
        result = get_commit_modified_files("abc123")
        assert result == ["file1.py", "file2.txt"]

    @patch('git.commands.run_git_command')
    def test_failure_exits(self, mock_git):
        mock_git.return_value = (False, "error")
        import pytest
        with pytest.raises(SystemExit):
            get_commit_modified_files("abc123")
