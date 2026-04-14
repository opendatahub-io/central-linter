"""Tests for config module: constants, dataclasses, logging."""

from unittest.mock import patch

from config import GitLabConfig, JiraConfig, ValidationResult


class TestValidationResult:
    def test_ok(self):
        result = ValidationResult.ok()
        assert result.success is True
        assert result.error_message is None

    def test_fail(self):
        result = ValidationResult.fail("Error occurred")
        assert result.success is False
        assert result.error_message == "Error occurred"


class TestGitLabConfig:
    def test_from_environment_all_vars(self):
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

    def test_defaults_when_no_env_vars(self):
        with patch.dict('os.environ', {}, clear=True):
            config = GitLabConfig.from_environment()
            assert config.project_id is None
            assert config.mr_iid is None
            assert config.base_sha == 'main'

    def test_lint_base_branch_fallback(self):
        with patch.dict('os.environ', {'LINT_BASE_BRANCH': 'develop'}, clear=True):
            config = GitLabConfig.from_environment()
            assert config.base_sha == 'develop'

    def test_ci_sha_takes_priority_over_lint_base_branch(self):
        with patch.dict('os.environ', {
            'CI_MERGE_REQUEST_DIFF_BASE_SHA': 'abc123',
            'LINT_BASE_BRANCH': 'develop',
        }, clear=True):
            config = GitLabConfig.from_environment()
            assert config.base_sha == 'abc123'


class TestJiraConfig:
    def test_from_environment_all_vars(self):
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

    def test_default_url(self):
        with patch.dict('os.environ', {
            'JIRA_USERNAME': 'user@example.com',
            'JIRA_API_TOKEN': 'secret-token',
        }, clear=True):
            config = JiraConfig.from_environment()
            assert config.site_url == 'https://redhat.atlassian.net'
            assert config.is_configured is True

    def test_strips_trailing_slash(self):
        with patch.dict('os.environ', {
            'JIRA_URL': 'https://jira.example.com/',
            'JIRA_USERNAME': 'user@example.com',
            'JIRA_API_TOKEN': 'secret-token',
        }):
            config = JiraConfig.from_environment()
            assert config.site_url == 'https://jira.example.com'

    def test_not_configured_missing_username(self):
        config = JiraConfig(site_url='https://jira.example.com', username=None, api_token='token')
        assert config.is_configured is False

    def test_not_configured_missing_token(self):
        config = JiraConfig(site_url='https://jira.example.com', username='user', api_token=None)
        assert config.is_configured is False

    def test_not_configured_missing_both(self):
        with patch.dict('os.environ', {}, clear=True):
            config = JiraConfig.from_environment()
            assert config.is_configured is False
