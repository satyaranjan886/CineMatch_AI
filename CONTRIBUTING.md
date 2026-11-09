# Contributing

Thanks for helping improve CineMatch AI.

## Ways to contribute

- Bug reports and fixes
- Documentation improvements
- Tests
- Features that fit the existing architecture

## Development setup

Follow the [README](README.md) Quick start. Then:

```bash
make lint
make test
```

## Pull requests

1. Fork the repo and create a branch from `main`
2. Keep changes focused and described clearly
3. Add or update tests when behavior changes
4. Run `make lint` and `make test` before opening a PR
5. Do not commit secrets, `.env` files, or personal credentials

## Code style

- Backend: Python 3.12+, Ruff for lint/format
- Frontend: TypeScript, ESLint, Next.js conventions
- Prefer small, reviewable diffs

## Community

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

If you find a vulnerability, follow [SECURITY.md](SECURITY.md). Do not file a public issue with exploit details.
