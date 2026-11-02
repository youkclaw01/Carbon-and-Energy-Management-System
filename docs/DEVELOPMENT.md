# Development and testing

## Principles
- Small, single-result work units; each unit is verified before the next depends on it.
- Local tests are not production verification. Only report what has actually been observed.
- Synthetic data only; secrets live outside the repository (key vault or local secret files that are never committed).

## Running tests
Tests are plain Python scripts under `services/tests/`; most run without cloud access, using in-memory stand-ins for SQL:

```bash
cd services
python3 tests/test_topo.py        # topology rules, 46 checks
python3 tests/test_cq.py          # central query
python3 tests/test_auth_api.py    # login, MFA, sign-up, grades
```
Run a script from `services/` so relative imports resolve. See each file's header for required environment variables.

## Coding conventions
- Readable code: short functions, explicit names, comments explain *why*.
- Each service keeps its HTTP layer thin and its decision logic in a `*_core.py` module that tests call directly.
- Error bodies and status words are part of the contract; changing them requires updating tests and the portal.
- Terminology in user-facing text: the acting party is "administrator or reviewer".

## Portal
`portal/site/` is plain HTML/CSS/JS with no build step. `portal/nginx.conf` defines the same-origin API routes. Static pages can be served locally with `python3 portal/devserve.py`.
