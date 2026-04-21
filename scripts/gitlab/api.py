"""GitLab API utilities for the AIPCC linter."""

from typing import List, Optional

import requests

from config import GitLabConfig
from log import logger


def get_mr_author(config: GitLabConfig) -> Optional[str]:
    """
    Fetch the merge request author username from GitLab API.

    Args:
        config: GitLab configuration

    Returns:
        Author username or None if unavailable
    """
    if not config.project_id or not config.mr_iid:
        return None

    if not config.api_url or not config.api_token:
        logger.warning("GitLab API credentials not available")
        return None

    headers = {"PRIVATE-TOKEN": config.api_token}
    url = f"{config.api_url}/projects/{config.project_id}/merge_requests/{config.mr_iid}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            mr_data = response.json()
            return mr_data.get("author", {}).get("username")
        else:
            logger.warning(f"API request failed with status {response.status_code}")
    except requests.RequestException as e:
        logger.warning(f"Could not fetch MR author: {e}")

    return None


def get_mr_commits_from_api(config: GitLabConfig) -> Optional[List[str]]:
    """
    Fetch the actual list of commit SHAs in the MR from GitLab API.

    This returns only the commits that are part of the MR, not commits
    from main that were merged after the feature branch was created.

    Args:
        config: GitLab configuration

    Returns:
        List of commit SHAs in the MR, or None if unavailable
    """
    if not config.project_id or not config.mr_iid:
        return None

    if not config.api_url or not config.api_token:
        logger.warning("GitLab API credentials not available, falling back to git log")
        return None

    headers = {"PRIVATE-TOKEN": config.api_token}
    url = f"{config.api_url}/projects/{config.project_id}/merge_requests/{config.mr_iid}/commits"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            commits_data = response.json()
            # Return commit SHAs in reverse order (oldest first, like git log)
            commit_shas = [commit["id"] for commit in reversed(commits_data)]
            logger.info(f"Fetched {len(commit_shas)} commits from GitLab API for MR {config.mr_iid}")
            return commit_shas
        else:
            logger.warning(f"API request for MR commits failed with status {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.warning(f"Could not fetch MR commits from API: {e}")
        return None
