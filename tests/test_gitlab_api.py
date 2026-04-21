"""Tests for gitlab.api module."""

import requests as requests_lib
from unittest.mock import Mock, patch

from config import GitLabConfig
from gitlab.api import get_mr_commits_from_api, get_mr_author


class TestGetMrCommitsFromApi:
    @patch('gitlab.api.requests.get')
    def test_success_reversed_order(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "abc123", "title": "Third"},
            {"id": "def456", "title": "Second"},
            {"id": "ghi789", "title": "First"},
        ]
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        result = get_mr_commits_from_api(config)
        assert result == ["ghi789", "def456", "abc123"]
        mock_get.assert_called_once_with(
            "https://gitlab.example.com/api/v4/projects/12345/merge_requests/678/commits",
            headers={"PRIVATE-TOKEN": "secret-token"},
            timeout=10
        )

    @patch('gitlab.api.requests.get')
    def test_404_returns_none(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None

    @patch('gitlab.api.requests.get')
    def test_network_error_returns_none(self, mock_get):
        mock_get.side_effect = requests_lib.RequestException("timeout")

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None

    def test_missing_project_id_returns_none(self):
        config = GitLabConfig(
            project_id=None, mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None

    def test_missing_api_token_returns_none(self):
        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token=None, base_sha="main"
        )
        assert get_mr_commits_from_api(config) is None


class TestGetMrAuthor:
    @patch('gitlab.api.requests.get')
    def test_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"author": {"username": "developer"}}
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        assert get_mr_author(config) == "developer"

    @patch('gitlab.api.requests.get')
    def test_failure(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = GitLabConfig(
            project_id="12345", mr_iid="678",
            api_url="https://gitlab.example.com/api/v4",
            api_token="secret-token", base_sha="main"
        )
        assert get_mr_author(config) is None

    def test_missing_config(self):
        config = GitLabConfig(
            project_id=None, mr_iid=None,
            api_url=None, api_token=None, base_sha="main"
        )
        assert get_mr_author(config) is None
