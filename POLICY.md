# Commit and Pull Request Guidelines

You must satisfy the following guidelines to submit code to our team's projects.  Keep in mind that your submission is reviewed by other team members who have expressed interest and expensed effort in reviewing your code.  It is incumbent upon you, as a submitter, to satisfy their review changes and requests.  If you have any questions or concerns, or require arbitration over code issues, please feel free to reach out to [prarit@redhat.com](mailto:prarit@redhat.com) for assistance.

1. **Each commit will represent one logical change.**  Large commits combining changes may be rejected by reviewers.
2. **Each commit and the Pull Request title field will begin with a valid JIRA ID.** The allowed JIRA projects that JIRA ID refers to include **RHELAI, RHOAIENG, AIPCC and INFERENG**. The INTERNAL keyword can be substituted for a Jira URL. The INTERNAL keyword indicates a change to code that is considered to have minimal customer impact such as timestamp changes for CI/CD files.  The INTERNAL keyword only works for files listed in a project's local .linterignore file.  A Jira is required to add files to the .linterignore file.
   1. CVEs should be referenced on a separate line as "CVE: \<CVE-ID\>".  If the commit contains multiple CVEs please include all CVE IDs as a comma separated list.
3. As recommended by Red Hat Legal, **each commit will have a Signed-off-by: from the author** acknowledging the Developer Certificate of Origin (DCO), [https://developercertificate.org](https://developercertificate.org).
   This can be done by setting the \-s flag for git-commit, and creating an alias.  For example,
   alias commit='git commit \-s'
   For those of you using an IDE, such as vscode, there appears to be functionality to set the Signed-off-by automatically: Vscode setting: `git.alwaysSignOff`.  Other IDEs seem to have this functionality (or provide a plugin for it).
4. **Each commit will contain a title, a description of change, and the previously mentioned Signed-off-by:.**  We acknowledge that this may be repetitive for simple commits, ie) A title may be "Fix typo" and the description may be "Fix typo."
5. Pull request merges contain the Pull Request Description and a list of who approved the PR.
6. AI Attribution is required, please read our [guidelines](https://docs.google.com/document/d/1fu0UEXeZXM6S3be6riBRHBi0PuchxtzhXZXXQQN9qO8/edit?tab=t.tpt43pk8cy4a).
