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

### Execution diagnostics

Each scanner summary includes `execution` with a fixed `status` (`exited`,
`timeout`, or `launch_error`), actual `returncode` or null, and bounded
`duration_ms`. The legacy integer result is unchanged: a wall timeout and a
launch error still fail the job. An actual scanner exit 124 is distinguished
from the runner's timeout. No raw log, exception message, path, or source text
is published.

`report_state` distinguishes `missing`, `invalid_json`, `unreadable`, and `json`.
The last value means JSON syntax parsed, **not** that the scanner schema is valid
or coverage complete. Schema validation, parser errors, fixpoint timeouts and
reviewed baselines retain their existing fail-closed behavior. Missing reports
still have null finding/input counts. The generic command default remains 600 seconds; the scanner-specific
Semgrep budget is documented below. Analysis flags remain unchanged. New diagnostics do not repair large-repository timeouts;
consumers pinned to an earlier action revision need a reviewed pin update.

### Measured large-source budget (infra273 / cbrapi8)

Semgrep and OpenGrep have a fixed 3600-second outer wall limit; Gitleaks and
Trivy retain 600-second process limits. The source workflow allows 90 minutes for
setup and all scanners. External callers must carry the same job budget when
updating their immutable action pin. `execution.wall_limit_seconds` records the actual
configured limit, separate from elapsed time and the scanner's own exit code.

On exact API source `4a1c03e` with Semgrep 1.182.0 and the pinned 1417-rule pack,
600 seconds ended without JSON. An otherwise identical 1200-second control
completed after 1198.323 seconds: 15913 inputs, 4777 candidate findings, 15 reported
errors (13 parser errors and 2 rule timeouts), plus 15 fixpoint timeouts. Later
revisions of the same source exceeded the 1800-second cap that followed that
measurement, and the private PIF repository without the retained state did the
same at 1800 seconds, so both scheduled and branch scans ended as tool_error.
The current 3600-second cap doubles the last observed 1800-second boundary and
keeps the same fail-closed behavior. This is an observed workload, not a
completion guarantee for arbitrary source or slow network/bootstrap.

Per-rule timeout 20 seconds, jobs 2, max-memory 512, source root and exclusions
are preserved. No findings, files or timeouts are suppressed. Any report with
parser/fixpoint errors remains PARTIAL/failure; a cap hit or missing/invalid
report remains tool_error/null. Candidate counts are not confirmed exploits.
Raw source, target paths and scanner diagnostics stay private.

The configured scanner maxima sum to 80 minutes (10 + 10 + 60). The final
90-minute caller budget leaves 10 minutes above those maxima for normal setup.
A shorter job budget is rejected by the RED budget contract because it could
interrupt the static analysis process before its configured cap after slow
earlier scanners. Bootstrap/network hard failures can still exhaust the finite job cap;
that remains a failed/unknown run, never a clean scan.
