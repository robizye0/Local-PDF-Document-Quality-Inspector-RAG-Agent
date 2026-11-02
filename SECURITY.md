# Security Policy

## Supported versions

Security fixes target the default branch. This repository is a portfolio and reference implementation; it is not a hosted service.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for this repository when available. If that channel is unavailable, contact the repository owner privately through GitHub and include:

- affected commit or version;
- reproduction steps or a minimal proof of concept;
- impact assessment;
- a suggested mitigation, if known.

Do not include API keys, tokens, passwords, personal data, or production documents in a report. Redact them as `[REDACTED]`.

## Security design notes

- Uploaded filenames are reduced to safe basenames and PDF payloads are size/signature checked.
- `SPECCHECK_API_KEY` enables API-key protection for `/api/*` routes.
- `CORS_ORIGINS` and `RATE_LIMIT_PER_MINUTE` are configurable deployment controls.
- Webhook payloads can be HMAC-SHA256 signed and retried; use an HTTPS endpoint.
- The default thread job store is process-local. Use the optional Celery/Redis adapter for durable workers.
- Do not expose the local development configuration directly to the public internet without authentication, TLS, retention controls, and monitoring.
