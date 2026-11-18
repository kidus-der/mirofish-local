# Security

MiroFish Local is designed to run on one trusted Mac. It has no login system, so keep every service on loopback and do not expose it through a tunnel, reverse proxy or public network address.

## Reporting a problem

Please use GitHub's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for a suspected data leak or sandbox bypass.

Useful reports include the affected commit, the steps to reproduce the problem and the expected impact. Remove personal data, private documents, tokens and machine details from your report.

## Before sharing results

Run:

```bash
python3 scripts/privacy-check.py
```

Do not publish raw `eval/results/e2e-*` folders, `backend/uploads`, `backend/logs`, `.env` or downloaded models.
