"""Tests for validators.merge_request module.

Ported from TestMergeRequestValidation, TestClosingPhrasePattern,
TestValidateNoProtectedTypeClosure, and test_full_mr_validation_success
from test_mr_commit_linter.py.
"""

import requests as requests_lib

import pytest
from unittest.mock import Mock, patch

from config import (
    CommitInfo, MergeRequestInfo, GitLabConfig, JiraConfig,
    CLOSING_PHRASE_PATTERN, JIRA_ID_EXTRACT_PATTERN,
)
from validators.merge_request import (
    validate_mr_title,
    validate_mr_description,
    validate_no_protected_type_closure,
)


# ============================================================================
# MERGE REQUEST VALIDATION TESTS
# ============================================================================

class TestMergeRequestValidation:
    def test_validate_mr_title_with_jira(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Feature implementation",
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_with_internal(self):
        mr_info = MergeRequestInfo(
            iid="123", title="INTERNAL: Documentation update",
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_invalid(self):
        mr_info = MergeRequestInfo(
            iid="123", title="Feature implementation",
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_mr_title_invalid_no_colon(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234 Feature implementation",
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must have a colon" in result.error_message

    def test_validate_mr_title_invalid_short_description(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "description is too short" in result.error_message

    def test_validate_mr_title_revert_with_valid_inner_title(self):
        mr_info = MergeRequestInfo(
            iid="123", title='Revert "AIPCC-1234: Fix authentication bug"',
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is True

    def test_validate_mr_title_revert_with_invalid_inner_title(self):
        mr_info = MergeRequestInfo(
            iid="123", title='Revert "Fix authentication bug"',
            description="Description", author="developer"
        )
        result = validate_mr_title(mr_info)
        assert result.success is False
        assert "must start with a Jira ticket" in result.error_message

    def test_validate_mr_description_valid(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description="This is a description",
            author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is True

    def test_validate_mr_description_valid_without_sob(self):
        """Signed-off-by is not required in MR descriptions (checked per-commit instead)."""
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description="This is a long description with no sign-off line.",
            author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is True

    def test_validate_mr_description_empty(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description=None, author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is False
        assert "description cannot be empty" in result.error_message

    def test_validate_mr_description_empty_string(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description="", author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is False
        assert "description cannot be empty" in result.error_message

    def test_validate_mr_description_whitespace_only(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Fix",
            description="   \n  ", author="developer"
        )
        result = validate_mr_description(mr_info)
        assert result.success is False
        assert "description cannot be empty" in result.error_message


class TestIntegrationMR:
    def test_full_mr_validation_success(self):
        mr_info = MergeRequestInfo(
            iid="123", title="RHELAI-1234: Feature implementation",
            description="This MR implements feature X.",
            author="developer"
        )
        assert validate_mr_title(mr_info).success is True
        assert validate_mr_description(mr_info).success is True


# ============================================================================
# CLOSING PHRASE PATTERN TESTS
# ============================================================================

class TestClosingPhrasePattern:
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
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == expected_ids

    def test_optional_colon_after_keyword(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Fixes: AIPCC-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert ids[0].upper() == "AIPCC-100"

    def test_comma_separated_ids(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Closes AIPCC-100, AIPCC-101")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101"]

    def test_and_separated_ids(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Resolves AIPCC-100 and AIPCC-101")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101"]

    def test_comma_and_separated_ids(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Fixed: AIPCC-100, AIPCC-101 and AIPCC-102")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101", "AIPCC-102"]

    def test_case_insensitive_keyword(self):
        for text in ["FIXES AIPCC-100", "fixes AIPCC-100", "Fixes AIPCC-100"]:
            matches = CLOSING_PHRASE_PATTERN.findall(text)
            assert len(matches) == 1, f"Failed for: {text}"

    def test_multiple_spaces_between_keyword_and_id(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Fixes   AIPCC-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert ids[0].upper() == "AIPCC-100"

    def test_various_project_keys(self):
        for key in ["RHELAI-1234", "RHOAIENG-5678", "AB-1", "PROJ_KEY-99"]:
            matches = CLOSING_PHRASE_PATTERN.findall(f"Fixes {key}")
            assert len(matches) == 1, f"Failed for key: {key}"

    def test_tab_separator_no_match(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Closes\tAIPCC-100")
        assert len(matches) == 0

    def test_colon_without_space_no_match(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Closes:AIPCC-100")
        assert len(matches) == 0

    def test_three_id_comma_list(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Closes AIPCC-100, AIPCC-101, AIPCC-102")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100", "AIPCC-101", "AIPCC-102"]

    def test_multiple_closing_phrases_in_text(self):
        text = "Closes AIPCC-100. Also fixes AIPCC-200"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 2
        assert JIRA_ID_EXTRACT_PATTERN.findall(matches[0]) == ["AIPCC-100"]
        assert JIRA_ID_EXTRACT_PATTERN.findall(matches[1]) == ["AIPCC-200"]

    def test_lowercase_jira_id_matches(self):
        matches = CLOSING_PHRASE_PATTERN.findall("fixes aipcc-100")
        assert len(matches) == 1
        ids = JIRA_ID_EXTRACT_PATTERN.findall(matches[0])
        assert [i.upper() for i in ids] == ["AIPCC-100"]

    def test_keyword_substring_unresolved_no_match(self):
        matches = CLOSING_PHRASE_PATTERN.findall("unresolved AIPCC-100")
        assert len(matches) == 0

    def test_no_match_bare_jira_id(self):
        matches = CLOSING_PHRASE_PATTERN.findall("AIPCC-100: Fix the bug")
        assert len(matches) == 0

    def test_no_match_jira_id_before_keyword(self):
        matches = CLOSING_PHRASE_PATTERN.findall("AIPCC-100: Fix authentication bug")
        assert len(matches) == 0

    def test_no_match_related_to(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Related to AIPCC-100")
        assert len(matches) == 0

    def test_no_match_see_also(self):
        matches = CLOSING_PHRASE_PATTERN.findall("See also AIPCC-100")
        assert len(matches) == 0

    def test_no_match_ref(self):
        matches = CLOSING_PHRASE_PATTERN.findall("Ref AIPCC-100")
        assert len(matches) == 0

    def test_no_cross_newline_match(self):
        text = "Ready to close\nAIPCC-100: Add feature"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 0

    def test_no_cross_newline_match_fix(self):
        text = "We need to fix\nAIPCC-100: Update config"
        matches = CLOSING_PHRASE_PATTERN.findall(text)
        assert len(matches) == 0

    def test_keyword_in_middle_of_word_no_match(self):
        matches = CLOSING_PHRASE_PATTERN.findall("prefix AIPCC-100")
        assert len(matches) == 0


# ============================================================================
# PROTECTED TYPE CLOSURE VALIDATION TESTS
# ============================================================================

class TestValidateNoProtectedTypeClosure:
    def _make_gitlab_config(self):
        return GitLabConfig(
            project_id='12345', mr_iid='678',
            api_url='https://gitlab.example.com/api/v4',
            api_token='gitlab-token', base_sha='main',
        )

    def _make_jira_config(self):
        return JiraConfig(
            site_url='https://jira.example.com',
            username='user@example.com', api_token='jira-token',
        )

    def _mock_jira_type(self, mock_get, type_map):
        def side_effect(url, **kwargs):
            resp = Mock()
            for key, issue_type in type_map.items():
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

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_epic_in_mr_description(self, mock_commits, mock_get):
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'AIPCC-100' in errors[0]
        assert 'Epic' in errors[0]
        assert 'MR description' in errors[0]

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'Closes AIPCC-100',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description',
    })
    def test_epic_in_mr_title(self, mock_commits, mock_get):
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'MR title' in errors[0]

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch('validators.merge_request.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description',
    })
    def test_epic_in_commit_message(self, mock_info, mock_commits, mock_get):
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123', title='AIPCC-999: Add feature',
            body='Resolves AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'commit message' in errors[0]

    # --- Non-detection tests ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-100: Fix the bug',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Related to AIPCC-100',
    })
    def test_bare_epic_id_passes(self, mock_commits, mock_get):
        mock_commits.return_value = []
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-200',
    })
    def test_non_epic_with_closing_keyword_passes(self, mock_commits, mock_get):
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-200': 'Story'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Closes AIPCC-200, AIPCC-100',
    })
    def test_mixed_epic_and_non_epic(self, mock_commits, mock_get):
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-200': 'Story', 'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        assert 'AIPCC-100' in errors[0]

    # --- Project key filtering ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes RHELAI-500',
    })
    def test_non_aipcc_ticket_skipped(self, mock_commits, mock_get):
        mock_commits.return_value = []
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    # --- Cross-boundary safety ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch('validators.merge_request.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'We need to close',
    })
    def test_no_cross_boundary_false_positive(self, mock_info, mock_commits, mock_get):
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123', title='AIPCC-100: Update config',
            body='Signed-off-by: Dev',
        )
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_get.assert_not_called()

    # --- Skip conditions ---

    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
        'CI_MERGE_REQUEST_LABELS': 'bug, skip-issue-type-check, urgent',
    })
    def test_skip_with_label(self, mock_commits):
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0
        mock_commits.assert_not_called()

    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
        'CI_MERGE_REQUEST_LABELS': 'skip-issue-type-check',
    })
    def test_skip_with_label_alone(self, mock_commits):
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_skip_with_missing_jira_credentials(self, mock_commits):
        jira_config = JiraConfig(
            site_url='https://jira.example.com', username=None, api_token=None,
        )
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), jira_config
        )
        assert len(errors) == 0

    @patch.dict('os.environ', {}, clear=True)
    def test_skip_when_running_locally(self):
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    # --- API failure handling ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_api_failure_skips_check_for_that_id(self, mock_commits, mock_get):
        mock_commits.return_value = []
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_network_failure_skips_check(self, mock_commits, mock_get):
        mock_commits.return_value = []
        mock_get.side_effect = requests_lib.RequestException("timeout")
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 0

    # --- Optional colon variant ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes: AIPCC-100',
    })
    def test_colon_variant_detects_epic(self, mock_commits, mock_get):
        mock_commits.return_value = []
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1

    # --- Commit fallback to git log ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch('validators.merge_request.get_commits_in_range')
    @patch('validators.merge_request.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description',
    })
    def test_fallback_to_git_log(self, mock_info, mock_range, mock_commits, mock_get):
        mock_commits.return_value = None
        mock_range.return_value = ['abc123 AIPCC-999: Add feature']
        mock_info.return_value = CommitInfo(
            commit_id='abc123', title='AIPCC-999: Add feature',
            body='Implements AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
        mock_range.assert_called_once()

    # --- Error message content ---

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'AIPCC-999: Add feature',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Fixes AIPCC-100',
    })
    def test_error_message_content(self, mock_commits, mock_get):
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

    @patch('jira.api.requests.get')
    @patch('validators.merge_request.get_mr_commits_from_api')
    @patch('validators.merge_request.get_commit_info')
    @patch.dict('os.environ', {
        'CI_MERGE_REQUEST_TITLE': 'INTERNAL: Update docs',
        'CI_MERGE_REQUEST_DESCRIPTION': 'Description',
    })
    def test_internal_commit_still_checked(self, mock_info, mock_commits, mock_get):
        mock_commits.return_value = ['abc123']
        mock_info.return_value = CommitInfo(
            commit_id='abc123', title='INTERNAL: Update docs',
            body='Closes AIPCC-100\n\nSigned-off-by: Dev',
        )
        self._mock_jira_type(mock_get, {'AIPCC-100': 'Epic'})
        errors = validate_no_protected_type_closure(
            self._make_gitlab_config(), self._make_jira_config()
        )
        assert len(errors) == 1
