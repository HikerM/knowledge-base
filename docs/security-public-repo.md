# Public Repository Security

This repository is public. Treat every committed file as permanently visible.

## Never Commit

- `.kb/` or `.kb/index.sqlite`
- `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm`
- `.env`, `.env.local`, or environment dumps
- `secrets.*`
- `private/`
- `tmp/`
- `exports/`
- real API keys, GitHub tokens, OpenAI keys, bearer tokens, passwords, private keys, customer data, production logs, or confidential project notes

## Required Pre-Push Checks

Run the validation suite before pushing:

```bash
python scripts/kb.py --help
python scripts/kb.py init
python scripts/kb.py index
python scripts/kb.py stats
python scripts/kb.py doctor
python scripts/kb.py benchmark
python scripts/kb.py audit
python scripts/kb.py secret-scan
python tests/smoke_test.py
python tests/search_quality_test.py
```

`secret-scan` checks common high-risk patterns including API key assignments, GitHub tokens, OpenAI keys, `password=`, `secret=`, private key blocks, bearer tokens, and accidental `.env` files. Findings are redacted in output. A high-risk finding returns a non-zero exit code.

Test fixtures may use fake values only when the line contains the explicit marker `TEST_ONLY_SECRET_PATTERN`.

## Why `.kb/index.sqlite` Is Not Committed

Markdown files are the source of truth. SQLite is a generated local index and may contain derived chunks from local notes. It must remain ignored and reproducible through:

```bash
python scripts/kb.py index
```

The public repository should contain code, configuration, docs, templates, and controlled test fixtures only.
