# Pinned source audit

The composite action defaults to Semgrep. Callers may explicitly set `engine: opengrep` to use the pinned standalone OpenGrep binary and immutable upstream rule archive, with the explicit compatibility setting below. No automatic engine fallback occurs. Gitleaks and Trivy, private raw reports, safe aggregate output, wall limits, and fail-closed timeout handling are unchanged.

Both engines disable inline suppression and project Semgrep ignore files. The Semgrep wheel remains a pinned bootstrap dependency for packing upstream YAML rules in the private environment; it is not the selected scan engine when `engine: opengrep` is set. Application dependencies and application code are never loaded.

Legacy version 1 parser policies remain valid for Semgrep. Version 2 policies bind the engine name and version explicitly:

```json
{
  "version": 2,
  "engine": "opengrep",
  "engine_version": "2.0.0",
  "rules_sha256": "<verified rules archive SHA256>",
  "accepted_parser_errors": []
}
```

Changing engine or source bytes requires a fresh review and matching identities; old acceptances are not transferred automatically. Only parser errors with exact source bytes, locations, multiplicity and tool/rules binding can be reviewed. Timeouts always fail, even when parser errors in the same report are known. Known parser counts remain visible alongside timeouts. PRs continue reading policy from their base commit.

Run contracts without loading the target repository:

```sh
python3 -I -m unittest discover -s scripts/security-ci -p 'test_*.py'
```

## Bounded scanner lifecycle

`entry.py` uses a source-backed restricted launcher when installed on claw;
otherwise it directly executes the audit on hosted/other runners. The claw
boundary authenticates actual runner ancestry and runs the entire audit as the
runner UID in a separate cgroup, not as root. Ceiling:2GiB RAM/256MiB swap,
45min runtime,10s stop grace; admission can lower RAM to preserve host/CI reserve
or visibly refuse when insufficient. Only one claw audit is admitted at a time.
The composite action always requests cleanup; a host job-completed hook and
independent systemd deadline cover death of the step wrapper. Cancelled,
OOM-killed, timed-out or refused scans do not count as completed coverage.

Each subprocess also gets a separate process group. On normal exit, timeout,
SIGTERM or SIGINT the wrapper sends TERM then KILL to remaining descendants
before discarding private scratch. Scanner concurrency starts at one worker.
The engine heap ceiling is512MiB for Semgrep and1024MiB for OpenGrep. This is
an engine operation bound, not a total process-tree cap; native caps still apply.

## Partial-run observations

The runner emits allowlisted one-line `Security audit checkpoint: ` JSON records
before and after each scanner, also appending them to the GitHub step summary.
These records preserve completed-stage aggregates if a later stage is cancelled
or killed. A `started` record is not evidence of completed coverage. Consumers
must not treat a checkpoint as the final audit result or infer success from a
missing later report. Raw paths, findings and scanner messages are never copied.

The legacy `timeouts` field counts fixpoint timeouts. Positive optional
`ordinary_timeouts` and `memory_errors` fields count known top-level timeout and
engine memory-error types separately. They contain integers only; unknown errors
still count toward `errors`, and partial reports still fail. An absent counter
does not establish completed coverage when the report itself is missing.

A handled cancellation retains earlier observations, marks the interrupted
scanner as `tool_error` with `execution.status=cancelled`, and returns the
nonzero signal status. SIGKILL can prevent a final record; earlier flushed
checkpoints still describe only the stages already observed.

## Independent stages

The optional `stage` input is `all` by default, preserving existing callers.
Use `sast` for the selected Semgrep/OpenGrep engine, `secrets` for Gitleaks,
or `dependencies` for Trivy. A stage downloads only its required tools;
non-SAST stages do not install the rule environment or consume parser policies.

On claw, independent stages must be separate GitHub jobs, not multiple action
invocations inside one Worker: each Worker identity owns one bounded audit.
Use a non-fail-fast matrix so one scanner failure does not cancel the others,
and keep an aggregate gate that requires every stage to succeed. Stage splitting
does not convert missing, cancelled, timed-out or partial analysis to success.

The claw launcher accepts an optional strictly enumerated stage field while
retaining legacy five-field requests. This never lets callers change the command,
UID or resource/deadline caps. Deploy that compatible host helper before opting
callers into stages. The default `all` entry keeps the legacy request shape.

The launcher supplies its remaining service budget as `SECURITY_RUNTIME_SECONDS`.
Downloads and subprocesses share this deadline and reserve 20 seconds for report
publication and descendant cleanup. Without the host budget, existing hosted
limits remain unchanged. SAST runs with zero scanned inputs fail explicitly, including the default `all` stage.
On claw, the entry relays only bounded allowlisted checkpoints from the owned
runner summary. Launcher exit zero without a finished valid scanner report, or
with a timed-out/failed execution, is an error; raw finding text is never relayed.

## Engine version migration

The self-audit workflow explicitly selects OpenGrep. Its former checked-in
1.32.0 policy had an empty parser-error list and exactly matched the default
engine/version/rules binding generated from the reviewed tool pins. Removing
that redundant empty file preserves the same policy record and digest; it does
not accept any parser errors or transfer an older engine's exceptions.

Upgrade in two reviewed changes: first remove the empty policy while retaining
the1.32.0 tool pin, then base the new engine-pin PR on the actual default-branch
commit containing that removal. PRs read the base policy; deleting the file and
changing the pin in one PR would still be rejected against an older base. A
consumer with its own tracked version-bound policy needs the same explicit
base-policy coordination before adopting a new action pin.

The generated policy binds the engine, version and immutable rules. Individual
reviewed parser-error identities bind source bytes and positions; this empty
policy contains none and does not prove exact-source coverage. Unaccepted parser
errors, rule/fixpoint timeouts, missing reports and zero targets retain their
existing failure behavior.

## Qualified opt-in OpenGrep 2

The opt-in binary is OpenGrep2.0.0, verified against the immutable official
release asset digest. Semgrep remains the default. Callers explicitly select
`engine: opengrep` and a reviewed action commit; no automatic fallback occurs.
The original rule archive, target/nosem/ignore settings, per-rule20-second
deadline, single worker, and native lifecycle/resource limits are unchanged.
OpenGrep gets a1024MiB internal heap ceiling; Semgrep retains512MiB.

For OpenGrep only, rule `dangerous-subprocess-use-tainted-env-args` disables
`symbolic_propagation`. Literal propagation can otherwise exclude an aliased
shell command from its generic sink without matching its shell-specific sink.
This conservative setting also restores some false-positive candidates for
literal executable aliases; findings remain candidates for review. Rule IDs,
sources, sinks, other options and all other rules stay unchanged. Packing rejects
a missing/duplicate pinned rule or unexpected upstream option drift. Default
Semgrep packing preserves the original rule content.

This release includes the precise Python raw-string/ReDoS correction
[OpenGrep901](https://github.com/opengrep/opengrep/pull/901). Its internal
taint fixpoint timeout has been removed; ordinary rule and native deadlines
still apply. Unaccepted parser errors, all reported rule/fixpoint timeouts,
missing reports and zero-target results keep their fail-closed behavior.
No older parser acceptance is transferred.

Qualification uses the upstream raw-string/numeric-escape/overflow regressions,
positive/negative findings, adversarial ignore/nosem controls, and exact target
and finding-occurrence comparison on affected original inputs. Reduced-input
checks are supplementary: each adopting consumer also needs complete source
validation bound to its actual source revision and the selected engine/rules.
