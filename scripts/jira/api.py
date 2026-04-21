"""Jira API utilities for the AIPCC linter."""

from typing import Optional

import requests

from config import JiraConfig
from log import logger


def get_jira_issue_type(issue_key: str, config: JiraConfig) -> Optional[str]:
    """
    Fetch the issue type for a Jira issue via the Jira Cloud REST API.

    Calls GET /rest/api/2/issue/{key}?fields=issuetype with HTTP Basic Auth.
    Returns the issue type name (e.g. "Epic", "Story", "Bug") or None if
    the lookup fails.
    """
    url = f"{config.site_url}/rest/api/2/issue/{issue_key}?fields=issuetype"
    try:
        response = requests.get(
            url,
            auth=(config.username, config.api_token),
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            issue_type = data.get("fields", {}).get("issuetype", {}).get("name")
            return issue_type
        else:
            logger.warning(
                f"Jira API request for {issue_key} returned status {response.status_code} - skipping issue type check."
            )
            return None
    except requests.RequestException as e:
        logger.warning(
            f"Jira API request for {issue_key} failed ({e}) - skipping issue type check."
        )
        return None
