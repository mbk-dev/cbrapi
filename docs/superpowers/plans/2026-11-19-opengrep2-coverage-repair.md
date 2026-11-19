# Opt-in OpenGrep 2 coverage repair

Scope: cbrapi17, supporting security96 and inspector16. Preserve global
security76 coordination and all existing operation grants/holds.

- [x] Qualify the digest-pinned new engine against original affected literals,
  upstream regressions, ignore/nosem controls and exact target/finding identity.
- [x] Reproduce the real self-audit policy/pin mismatch with an integration test.
- [x] First publish the empty-policy preparation with the existing1.32.0 pin.
  Prove generated checkout policy equals the removed file, and existing PR-base
  policy still validates. Preserve fail-closed parser handling.
- [ ] Base the separate2.0.0 pin change on the delivered preparation, obtain
  independent review and preserve Semgrep as the action default.
- [ ] Adopt the immutable action revision explicitly in the consumer and require
  complete exact-source qualification before any acceptance/cutover claim.

Only trusted security tooling runs; application files/hooks/dependencies are
never executed. Raw reports and runtime receipts stay outside Git.
