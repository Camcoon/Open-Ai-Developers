# Recently edited

This log was moved from the project root into `docs/`.

| File | Lines | Edit |
| --- | --- | --- |
| `app/main.py` | 6–10, 43–55, 82–87 | Disable public built-in docs; expose Swagger/OpenAPI through admin-protected routes and return HTTP 401 for denied requests. |
| `app/seed.py` | 28–43 | Idempotently seed the `admin` account (`admin@example.com`, password `admin`, role `admin`) even when the database already has other users. |
| `app/cli.py` | 58 | Print the seeded admin login after initialization. |
| `app/templates/authenticated-base.html` | 9–14 | Show the API docs navigation link only to authenticated admin users. |
| `app/templates/app.html` | 11–15 | Display the OpenAPI docs link on the user home page only for admins. |
| `README.md` | 19–30 | Document admin-only OpenAPI access and the seeded admin account; retain the four-column seeded-accounts table. |
| `tests/test_scenario.py` | 47–83 | Verify docs links are hidden from HODs, anonymous/HOD users cannot access docs or schema, and admins can. |
| `app/services/allocations.py` | 17–24, 68–113 | Import capacity and ranking helpers; retain request validation and TA load calculations; centralize persistence with selected-TA revalidation. |
| `app/services/allocations.py` | 146–190 | Route manual assignments through `_persist_assignment`, validating department budget and TA capacity before commit. |
| `app/services/allocations.py` | 193–293 | Validate requests before candidate discovery, filter capacity-ineligible TAs, rank via `get_strategy(mode).rank(...)`, and persist through the shared helper. |
| `app/services/capacity_guard.py` | 1–32 | Keep request-budget validation, TA-cap validation, and capacity-based candidate filtering. |
| `app/services/strategies.py` | 11–101 | Provide experience-first, least-loaded, and round-robin candidate-ranking strategies. |
| `tests/test_strategies.py` | 1–167 | Cover ranking behavior and strategy selection, including unsupported modes. |
| `tests/test_scenario.py` | 86–100 | Verify candidate and review-board views report matching TA capacity values. |
| `tests/test_scenario.py` | 112–161 | Verify validation-before-candidate-filtering, selected-TA revalidation before persistence, and capacity-safe auto selection. |
| `tests/test_scenario.py` | 164–275 | Retain strategy-based auto-allocation coverage for ranking, capacity limits, budgets, unsupported modes, and no eligible TAs. |
| `tests/conftest.py` | 21–24 | Add a `db_session` fixture alias for the existing isolated in-memory test session. |
| `tests/test_integration.py` | 64–148 | Add TestClient coverage for successful manual assignments and rejection for TA-cap and department-budget violations; mock HOD lookup and use the fixture database engine. |
| `test_guard.py` | 1–16 | Keep the manual capacity-guard smoke test. |
