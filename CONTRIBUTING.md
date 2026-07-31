# Contributing

Contributions that make the workflow safer, more portable, more measurable or
easier to operate are welcome.

## Before opening a pull request

1. Open an issue for substantial changes to scoring, publication safety,
   analytics semantics, data models or production integrations.
2. Keep production credentials, tenant identifiers, article evidence and
   customer data out of commits, fixtures, screenshots and issue text.
3. Add or update tests for deterministic logic.
4. Update the relevant contract or runbook when behaviour changes.
5. Run the checks below.

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 scripts/validate_bundle.py
git diff --check
```

## Pull-request expectations

Describe the problem, the behavioural change, validation performed and any
remaining operational risk. Keep unrelated changes in separate pull requests.

By submitting a contribution, you agree that it may be distributed under the
Apache License 2.0.

## Security reports

Do not open a public issue for a suspected vulnerability or credential leak.
Use GitHub's private vulnerability-reporting channel when it is available, or
contact the repository owner privately.
