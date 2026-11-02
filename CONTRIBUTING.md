# Contributing

Thanks for helping improve SpecCheck.

## Development setup

1. Use Python 3.10+.
2. Install backend dependencies from `backend/requirements.txt`.
3. Start Ollama locally for end-to-end inference, or use `DEMO_MODE=true` for a deterministic no-model smoke test.
4. Run the checks before opening a pull request:

```bash
python -m pytest -q
python -m black --check backend
python -m isort --check-only backend
python -m flake8 --max-line-length=100 --exclude=__pycache__ backend
python -m mypy --ignore-missing-imports backend
pytest tests/evals -q
```

## Pull requests

- Keep changes focused and add regression tests for behavior changes.
- Do not commit PDFs, local Chroma data, reports, logs, credentials, or tokens.
- Preserve the local no-Redis/no-external-API development path unless the change is explicitly optional.
- Document production limitations honestly; do not claim a distributed feature is complete when it is only an adapter or fallback.
- Include the exact verification commands and results in the pull request description.

## Security

Never preserve API keys, tokens, passwords, private keys, or customer documents. Replace sensitive values with `[REDACTED]` and follow `SECURITY.md` for vulnerability reports.
