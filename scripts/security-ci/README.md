# Pinned source audit

The composite action defaults to Semgrep. Callers may explicitly set `engine: opengrep` to use the pinned standalone OpenGrep binary with the same immutable upstream rules. No automatic engine fallback occurs. Gitleaks and Trivy, private raw reports, safe aggregate output, wall limits, and fail-closed timeout handling are unchanged.

Both engines disable inline suppression and project Semgrep ignore files. The Semgrep wheel remains a pinned bootstrap dependency for packing upstream YAML rules in the private environment; it is not the selected scan engine when `engine: opengrep` is set. Application dependencies and application code are never loaded.

Legacy version 1 parser policies remain valid for Semgrep. Version 2 policies bind the engine name and version explicitly:

```json
{
  "version": 2,
  "engine": "opengrep",
  "engine_version": "1.32.0",
  "rules_sha256": "<verified rules archive SHA256>",
  "accepted_parser_errors": []
}
```

Changing engine or source bytes requires a fresh review and matching identities; old acceptances are not transferred automatically. Only parser errors with exact source bytes, locations, multiplicity and tool/rules binding can be reviewed. Timeouts always fail, even when parser errors in the same report are known. Known parser counts remain visible alongside timeouts. PRs continue reading policy from their base commit.

Run contracts without loading the target repository:

```sh
python3 -I -m unittest discover -s scripts/security-ci -p 'test_*.py'
```
