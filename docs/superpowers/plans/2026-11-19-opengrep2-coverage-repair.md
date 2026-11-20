# Opt-in OpenGrep 2 coverage repair

Scope: cbrapi17, supporting security96 and inspector16. Preserve global
security76 coordination and all existing operation grants/holds.

- [x] Qualify the digest-pinned new engine against original affected literals,
  upstream regressions, ignore/nosem controls and exact target/finding identity.
- [x] Reproduce the real self-audit policy/pin mismatch with an integration test.
- [x] First publish the empty-policy preparation with the existing1.32.0 pin.
  Prove generated checkout policy equals the removed file, and existing PR-base
  policy still validates. Preserve fail-closed parser handling.
- [x] Base the separate2.0.0 pin change on the delivered preparation, obtain
  independent review and preserve Semgrep as the action default.
- [x] Adopt the immutable action revision explicitly in the consumer and require
  complete exact-source qualification before any acceptance/cutover claim.

Consumer qualification also exposed an alias regression in the upstream
environment-to-subprocess rule. Symbolic propagation excludes an aliased shell
command from the generic sink without matching the shell-specific sink. An
option-only repair is superseded: disabling propagation also misses aliases of
sources such as `os.getenv`. Preserve all options and sources; relax only the
two generic-sink literal-head exclusions for interpreters. Keep Semgrep unchanged.

- [x] Reproduce the alias omission with a static scanner fixture and failing
  engine-selection/compatibility tests in `scripts/security-ci/test_engines.py`
  and `test_run.py`; never execute the fixture.
- [x] Pass the explicit selected engine into `run.py --pack` and reject unknown
  engines and upstream binding/option drift.
- [x] Verify the original upstream scanner fixture and the two positive alias
  cases, the full controller suite, Ruff, and an independent diff review.
- [x] Complete actual consumer CI; retain errors as failures and keep runtime
  evidence outside Git. Any heap-limit change first needs separate qualification.

The legacy `timeouts` aggregate counts fixpoint timeouts only. Add optional,
positive `ordinary_timeouts` and `memory_errors` counters for known top-level
error types in `summary.py`, and allow their integer counts through the existing
checkpoint validator. Preserve the old aggregate and baseline equations. Tests
in `test_summary.py` and `test_checkpoint_transport.py` must prove redaction,
malformed-value rejection, and that partial execution still fails.

Qualify an OpenGrep-only1024MiB heap ceiling with one worker and the existing
20-second per-rule timeout; keep Semgrep at512MiB and preserve the host's native
memory/deadline guards. Component qualification does not replace consumer CI.

Follow-up source-alias qualification:

- [x] Reproduce the option-only source-alias omission; extend the static fixture
  with a source alias, tuple interpreter alias and three safe executable aliases.
- [x] Preserve symbolic propagation and copy/relax only two interpreter sink
  exclusions; reject missing, duplicate and malformed exclusion bindings.
- [x] Verify both independent negative controls, all four dangerous and three
  safe cases, upstream fixtures, default packing,91 contracts and Ruff.
- [x] Obtain an independent review of the monotonic sink change, deliver the
  corrected action revision, then require genuine complete consumer CI.

Only trusted security tooling runs; application files/hooks/dependencies are
never executed. Raw reports and runtime receipts stay outside Git.
