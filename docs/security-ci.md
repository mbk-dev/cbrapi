# Recurring source security checks

Task: https://github.com/mbk-dev/cbrapi/issues/6

`Security source audit` runs on relevant PR/push changes, weekly and manually.
It uses pinned Trivy (including development dependencies), Gitleaks (full Git
history or PR range) and Semgrep (immutable upstream rules). Tool archives
and wheel digests are verified before execution. Trivy refreshes its database.
The GitHub-hosted runner has read-only contents access, no persisted checkout
credentials, no production credentials and never installs or executes this
application. No deployment workflow is present.

Findings are advisory. Bootstrap/tool/JSON failures, new parser errors and
timeouts fail the job. Missing exact dependency input is `coverage_gap`,
with a null finding count, not a claim of zero vulnerabilities. Only sanitized
counts/status/tool provenance are published, never source paths, snippets,
error messages or secrets. Raw files stay private on the ephemeral runner;
no report artifacts are uploaded.

A parser baseline can only contain manually reviewed, exact source-byte,
position, occurrence-count and tool/rule-bound identities. Known errors stay
visible as `partial_known`; findings are never suppressed. PRs read the base
commit's baseline, not the candidate policy. Timeouts and zero targets cannot
be accepted. This initial rollout has no accepted parser errors.

This checks discovered source inputs, not deployed environments, host OS,
issuer revocations or vulnerability reachability. Unlocked/vendored and
unsupported inputs need separate review; no library lockfile is added for CI.

Verify the summary/privacy/baseline contract locally:

```sh
python3 -I -m unittest discover -s scripts/security-ci -p 'test_*.py'
```

Semgrep Fixpoint timeout diagnostics from `time.fixpoint_timeouts` contribute
to errors and a separate timeout count. They cannot be accepted by a parser
baseline and keep the job PARTIAL/failing. The contract has 29 unit tests.

## Reusable action

The composite action at .github/actions/security-audit executes this reviewed
package against the caller workspace. Callers pin its full commit SHA and pass
the pull-request base SHA. Its code stays outside the scanned workspace, and
no caller application dependencies or credentials are needed. Tool/rule archive
digests remain verified by the runner. Changing the action pin requires review.
The source in this canonical repository continues to audit itself directly.

The contract step runs in the action tree with isolated Python module search.
The scanner entry point ignores inherited Python environment/user site settings.
All tool/bootstrap child processes run beside their private logs, not inside
the target project, so target modules cannot shadow Python bootstrap modules.
A real adversarial-module regression test proves the failure before the fix.
The action directory depth is part of the reviewed metadata contract.

The orchestration tests call audit() through controlled download/process boundaries and real report parsing, baseline, JSON output and exit aggregation. Removing failure aggregation makes nine assertions fail; advisory findings retain exit zero. No scanner/bootstrap runtime code changed in this test-only revision.
