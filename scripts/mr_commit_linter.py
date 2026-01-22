#!/usr/bin/env python3

import os
import re
import subprocess
import sys
import importlib.resources
import requests

from messages import error


def contains_signed_off_by(body):
    for _line in body.splitlines():
        # There is no strict policy about where the SOB has to be, and it may not necessarily
        # be the last line in a description.  Other tags, such as Reported-by: or Reviewed-by:
        # may come after the SOB.
        sobpattern = re.compile(r"Signed-off-by: ", flags=re.MULTILINE)
        if sobpattern.findall(_line):
            return True
    return False


def get_mr_author():
    project_id = os.getenv("CI_PROJECT_ID")
    mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
    
    if not project_id or not mr_iid:
        return None
    
    headers = {"PRIVATE-TOKEN": os.getenv("GITLAB_API_TOKEN")}
    url = f"{os.getenv('CI_API_V4_URL')}/projects/{project_id}/merge_requests/{mr_iid}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            mr_data = response.json()
            author_username = mr_data.get("author", {}).get("username")
            return author_username
        else:
            print(f"API request failed with status {response.status_code}")
    except Exception as e:
        print(f"Warning: Could not fetch MR author: {e}")
    
    return None


bot_names = ["platform-engineering-bot", "aipcc-cicd-bot"]
mr_author = get_mr_author()
if (
    os.getenv("GITLAB_USER_LOGIN") in bot_names
    or os.getenv("GITLAB_USER_NAME") in bot_names
    or (mr_author and mr_author in bot_names)
):
    print("MR by renovate, ignoring")
    sys.exit(0)

mrtitle = os.getenv("CI_MERGE_REQUEST_TITLE")
if mrtitle is None:
    mrtitle = "local branch"

AIPCCPolicyDocMessage = "See https://docs.google.com/document/d/1TAicyqGKKELzaYL4o-Plz2s7tFUhOctZFzHErMQSc8c for AIPCC Commit and Merge Request Guidelines."
JIRA_PATTERN = re.compile(r"((RHELAI|RHOAIENG|AIPCC|INFERENG|RHAIENG)-\d+)", flags=re.MULTILINE)
JIRA_INTERNAL = re.compile(r"INTERNAL", flags=re.MULTILINE)
base_sha = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", "main")
mrid = os.getenv("CI_MERGE_REQUEST_IID", "(local branch)")

# verify that each commit title in the MR begins with a Jira ID
cmd = ["git", "log", "--oneline", "--no-merges", f"{base_sha}.."]
git_cmd = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
commits = git_cmd.stdout.decode("utf-8")
print(f"The commits in Merge Request {mrid} are:")
print(commits)
print("---")

for commit in commits.splitlines():
    commitid = commit.split(" ")[0]

    # check that the title contains a Jira Ticket ID
    title = commit.partition(" ")[2]
    if not JIRA_PATTERN.findall(title):
        if not JIRA_INTERNAL.findall(title):
            error(
                f"ERROR: Commit {commitid}: title must begin with a valid Jira ticket (RHELAI,RHOAIENG, AIPCC, INFERENG, RHAIENG or INTERNAL).\n{AIPCCPolicyDocMessage}"
            )
            sys.exit(1)

        # The Jira ticket id is INTERNAL.  Compare the modified files to the files in
        # https://gitlab.com/platform-engineering-org/gitlab-ci/-/raw/main/lint/config/linterignore
        # This file contains the names of files that can be modified when using
        # INTERNAL.

        linterignorecontents = []
        try:
            linterignore_path = importlib.resources.files("lint").joinpath("config/linterignore")
            with linterignore_path.open('r') as file:
                linterignorecontents = file.read()
        except FileNotFoundError:
            print(f"ERROR: Unable to find linterignore file from acessing resources in {linterignore_path}")
            sys.exit(1)
        except PermissionError:
            print(f"ERROR: No permission to read file from {linterignore_path}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)

        # read the files from linterignore
        internal_files = [line.strip() for line in linterignorecontents.splitlines()]

        # add directory contents to internal_files
        for internal_file in internal_files:
            if internal_file.endswith("/*"):
                directory = internal_file[:-2]
                if os.path.isdir(directory):
                    for dirpath, _dirnames, filenames in os.walk(directory):
                        for file in filenames:
                            internal_files.append(os.path.join(dirpath, file))

        # This output is useful on linter failures.
        print(f"Files that can be modified using INTERNAL: {internal_files}")

        # Do not attempt to verify that the files in .linterignore actually exist. The
        # CI/CD team prefers to keep a single .linterignore file instead of one per
        # repository.

        # get the list of files modified by the commit
        cmd = ["git", "show", "--numstat", '--pretty="%n"', f"{commitid}"]
        git_cmd = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        body = git_cmd.stdout.decode("utf-8")
        # the output of this command typically looks like
        # 28   9        test/jira_ticket_linter.py
        # 32   10       Makefile
        #               ^^^ _line.split()[2] is the filename

        for _line in body.splitlines():
            if _line.strip() == "" or _line.strip() == '"':
                continue
            if _line.split()[2] == "lint/config/linterignore":
                error(
                    f"ERROR: commit {commitid} lint/config/linterignore changes cannot be made with INTERNAL -- a JIRA must be used to modify this file.\n{AIPCCPolicyDocMessage}"
                )
                sys.exit(1)

            if _line.split()[2] not in internal_files:
                error(f"ERROR: {_line.split()[2]} is not in {linterignore_path}")
                sys.exit(1)

    # check that each commit has a Signed-off-by: tag
    cmd = ["git", "log", "-1", f"{commitid}", "--format='%b'"]
    git_cmd = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    body = git_cmd.stdout.decode("utf-8")
    print(f"{commitid}:\n{body}\n")
    if not contains_signed_off_by(body):
        error(
            f"ERROR: Commit {commitid}: commit does not contain a Signed-off-by: tag.\n{AIPCCPolicyDocMessage}"
        )
        sys.exit(1)

    # check that each commit has a body of at least three lines (ie, body is at
    # least one line, an empty line, and a Signed-off-by:)
    body_lines = body.count("\n")
    if body_lines < 3:
        error(
            f"ERROR: Commit {commitid}: description must be at least three lines in length (a description, an empty line, and a Signed-off-by:.\n{AIPCCPolicyDocMessage}"
        )
        sys.exit(1)

# verify that the Merge Request title begins with a Jira ID
if mrtitle != "local branch" and not JIRA_PATTERN.findall(mrtitle) and not JIRA_INTERNAL.findall(mrtitle):
    error(
        f"ERROR: Merge Request {mrid}: title must begin with a valid Jira ticket (RHELAI, RHOAIENG, AIPCC, INFERENG, RHAIENG or INTERNAL).\n{AIPCCPolicyDocMessage}"
    )
    sys.exit(1)

if mrtitle != "local branch":
    mrdescription = os.getenv("CI_MERGE_REQUEST_DESCRIPTION")
    if mrdescription is None:
        error(
            f"ERROR: Merge Request {mrid}: description cannot be empty.\n{AIPCCPolicyDocMessage}"
        )
        sys.exit(1)
    if not contains_signed_off_by(mrdescription):
        error(
            f"ERROR: Merge Request {mrid}: description does not contain a Signed-off-by: tag.\n{AIPCCPolicyDocMessage}"
        )
        sys.exit(1)
