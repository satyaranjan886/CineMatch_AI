# Load tests

Locust suite for concurrent HTTP testing against local/staging APIs.

```bash
.venv/bin/pip install -r requirements/loadtest.txt
./scripts/run_loadtest.sh low
```

Use only against local or private staging — never public production.  
Results are written to `loadtests/results/` (gitignored).
