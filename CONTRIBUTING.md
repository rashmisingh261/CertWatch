# Contributing to CertWatch

Thanks for helping! CertWatch is intentionally small; changes that keep it simple, secure and well tested are the easiest to merge.

## Development setup

Prerequisites: Python 3.11+, Node.js 22+ (Docker is optional).

```bash
git clone https://github.com/rashmisingh261/CertWatch.git && cd CertWatch

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm ci
npm run dev                                   # http://localhost:5173
```

To work on the UI without internet access, real domains or an existing database, run the demo backend instead
(`backend/.venv/bin/python scripts/demo.py serve`; see [docs/demo.md](docs/demo.md)).

## Code style

- **Python:** [Ruff](https://docs.astral.sh/ruff/) (configured in `backend/pyproject.toml`: line length 120, pycodestyle, pyflakes, isort, bugbear).
  Use type hints. Keep HTTP routes thin and put logic in `services/`.
- **TypeScript/React:** strict TypeScript and ESLint (`npm run lint`). Function components and hooks; API calls go through `src/api/client.ts`.
- Don't reformat or rewrite working code purely for style, and keep unrelated changes out of a pull request.
- No new dependencies unless they clearly earn their place.

## Testing requirements

Every change that alters behaviour needs tests, and **tests must never touch the real network or real certificates.**

```bash
# Backend
cd backend
ruff check --config pyproject.toml . ../scripts
pytest

# Frontend
cd frontend
npm run lint && npm test && npm run build
```

- Use generated certificates (`backend/tests/certgen.py`, `fakenet.py`) and mock DNS/TLS underneath the real inspection code (`FakeNet`).
- Frontend tests mock `fetch`.
- Bug fixes should come with a test that fails without the fix.
- Never commit real certificates, private keys, `.env` files or databases.

## Security-sensitive areas

Please take extra care (and call it out in your pull request) when touching `core/validation.py`, `core/network_guard.py`,
`services/inspector.py`, `services/runner.py`, `core/upload_limit.py`, or anything that opens a network connection or parses
uploaded data. Keep the invariants: port 443 only, all resolved addresses public, connect to the validated IP, bounded time and size.
Report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## Pull request guidelines

1. Open an issue first for anything larger than a small fix, so we can agree on the approach.
2. Branch from `main`; keep the pull request focused and small.
3. Make sure lint, tests and the build pass locally; CI runs them on every pull request.
4. Update the README/docs and add a line to `CHANGELOG.md` under *Unreleased* for user-visible changes.
5. Describe *what* changed and *why*, and how you tested it.
6. Be kind in reviews; we are all here to build something useful.

By contributing you agree that your contributions are licensed under the project's [MIT License](LICENSE).
