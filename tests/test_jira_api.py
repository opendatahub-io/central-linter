"""Tests for jira.api module."""

import requests as requests_lib
from unittest.mock import Mock, patch

from config import JiraConfig
from jira.api import get_jira_issue_type


class TestGetJiraIssueType:
    def _make_config(self):
        return JiraConfig(
            site_url='https://jira.example.com',
            username='user@example.com',
            api_token='secret-token',
        )

    @patch('jira.api.requests.get')
    def test_returns_issue_type(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'fields': {'issuetype': {'name': 'Epic'}}
        }
        mock_get.return_value = mock_response

        result = get_jira_issue_type('AIPCC-100', self._make_config())
        assert result == 'Epic'
        mock_get.assert_called_once_with(
            'https://jira.example.com/rest/api/2/issue/AIPCC-100?fields=issuetype',
            auth=('user@example.com', 'secret-token'),
            timeout=10,
        )

    @patch('jira.api.requests.get')
    def test_returns_story_type(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'fields': {'issuetype': {'name': 'Story'}}
        }
        mock_get.return_value = mock_response

        result = get_jira_issue_type('AIPCC-200', self._make_config())
        assert result == 'Story'

    @patch('jira.api.requests.get')
    def test_404_returns_none(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_jira_issue_type('AIPCC-999', self._make_config())
        assert result is None

    @patch('jira.api.requests.get')
    def test_network_error_returns_none(self, mock_get):
        mock_get.side_effect = requests_lib.RequestException("Connection timeout")

        result = get_jira_issue_type('AIPCC-100', self._make_config())
        assert result is None

    @patch('jira.api.requests.get')
    def test_401_returns_none(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = get_jira_issue_type('AIPCC-100', self._make_config())
        assert result is None
