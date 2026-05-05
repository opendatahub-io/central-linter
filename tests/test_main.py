"""Tests for main module.

Ported from TestValidateAllCommits in test_mr_commit_linter.py,
plus new tests for check_bot_exemption and validate_merge_request.
"""

from unittest.mock import patch

from config import CommitInfo, GitLabConfig
from main import check_bot_exemption, validate_all_commits, validate_merge_request


class TestCheckBotExemption:
    @patch('main.get_mr_author')
    @patch.dict('os.environ', {'GITLAB_USER_LOGIN': 'platform-engineering-bot'})
    def test_bot_user_login(self, mock_author):
        mock_author.return_value = None
        assert check_bot_exemption() is True

    @patch('main.get_mr_author')
    @patch.dict('os.environ', {'GITLAB_USER_NAME': 'aipcc-cicd-bot'}, clear=True)
    def test_bot_user_name(self, mock_author):
        mock_author.return_value = None
        assert check_bot_exemption() is True

    @patch('main.get_mr_author')
    @patch.dict('os.environ', {}, clear=True)
    def test_bot_via_api(self, mock_author):
        mock_author.return_value = 'platform-engineering-bot'
        assert check_bot_exemption() is True

    @patch('main.get_mr_author')
    @patch.dict('os.environ', {'GITLAB_USER_LOGIN': 'developer', 'GITLAB_USER_NAME': 'Dev User'})
    def test_non_bot_returns_false(self, mock_author):
        mock_author.return_value = 'developer'
        assert check_bot_exemption() is False


class TestValidateAllCommits:
    @patch('main.get_mr_commits_from_api')
    @patch('main.get_commit_info')
    @patch('main.validate_commit')
    @patch('main.run_git_command')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_uses_api(self, mock_git, mock_validate, mock_get_info, mock_api):
        mock_api.return_value = ["abc123", "def456"]
        mock_git.return_value = (True, "abc123 RHELAI-1234: Commit 1")
        mock_get_info.return_value = CommitInfo(
            commit_id="abc123", title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )
        mock_validate.return_value = []

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        errors = validate_all_commits(config)
        mock_api.assert_called_once_with(config)
        assert errors == []

    @patch('main.get_mr_commits_from_api')
    @patch('main.get_commits_in_range')
    @patch('main.get_commit_info')
    @patch('main.validate_commit')
    @patch('main.run_git_command')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_fallback_to_git_log(self, mock_git, mock_validate,
                                  mock_get_info, mock_get_range, mock_api):
        mock_api.return_value = None
        mock_get_range.return_value = [
            "abc123 RHELAI-1234: Commit 1",
            "def456 RHELAI-1235: Commit 2"
        ]
        mock_git.return_value = (True, "abc123 RHELAI-1234: Commit 1")
        mock_get_info.return_value = CommitInfo(
            commit_id="abc123", title="RHELAI-1234: Test",
            body="Test\n\nSigned-off-by: Dev"
        )
        mock_validate.return_value = []

        config = GitLabConfig(
            project_id=None, mr_iid=None,
            api_url=None, api_token=None, base_sha="main"
        )
        errors = validate_all_commits(config)
        mock_api.assert_called_once_with(config)
        mock_get_range.assert_called_once_with("main")
        assert errors == []

    @patch('main.get_mr_commits_from_api')
    @patch.dict('os.environ', {'CI_MERGE_REQUEST_IID': '123'})
    def test_no_commits(self, mock_api):
        mock_api.return_value = []

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        errors = validate_all_commits(config)
        assert errors == []


class TestValidateMergeRequest:
    @patch.dict('os.environ', {}, clear=True)
    def test_no_mr_title_returns_empty(self):
        errors = validate_merge_request()
        assert errors == []

    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'RHELAI-1234: Feature implementation',
        'CI_MERGE_REQUEST_IID': '123',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description\n\nSigned-off-by: Dev <dev@redhat.com>',
    })
    def test_valid_mr(self):
        errors = validate_merge_request()
        assert errors == []

    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'Bad title',
        'CI_MERGE_REQUEST_IID': '123',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description\n\nSigned-off-by: Dev',
    })
    def test_invalid_title(self):
        errors = validate_merge_request()
        assert len(errors) > 0
