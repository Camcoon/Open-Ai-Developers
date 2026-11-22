# Recently edited

This log was moved from the project root into `docs/`.

| File | Lines | Edit |
| --- | --- | --- |
| `app/main.py` | 6, 13, 28–30, 42–53 | Restore admin-protected Swagger UI and OpenAPI schema routes while disabling FastAPI's public built-in docs. |
| `app/main.py` | 81–87 | Return the existing unauthorized page with HTTP 401 so denied docs requests are not reported as successful. |
| `app/seed.py` | 28–43 | Idempotently seed the `admin` account (`admin@example.com`, password `admin`, role `admin`) even when the database already has other users. |
| `app/cli.py` | 58 | Print the seeded admin login after initialization. |
| `app/templates/authenticated-base.html` | 9–12 | Show the API docs navigation link only to admin users. |
| `app/templates/app.html` | 11–14 | Display the OpenAPI docs link on the user home page only for admins. |
| `README.md` | 19–30 | Document admin-only OpenAPI access and the seeded admin account. |
| `tests/test_scenario.py` | 35–73 | Verify docs links are hidden from HODs, anonymous/HOD users cannot access docs or schema, and admins can. |
| `app/services/allocations.py` | 17, 113–219 | Resolve conflicts by retaining request budget checks before candidate filtering, TA capacity filtering, and selected-TA revalidation before persistence. |
| `app/services/allocations.py` | 65–112, 220–245 | Extract shared request-error and TA capacity calculations for assignment and candidate/review views. |
| `tests/test_scenario.py` | 75–89 | Verify candidate and review-board views report matching TA capacity values. |
| `tests/test_scenario.py` | 92–153 | Resolve conflicts while retaining the admin-doc and capacity tests, including validation order, selected-TA revalidation, and capacity-safe auto selection. |
| `tests/conftest.py` | 21–24 | Add a `db_session` fixture alias for the existing isolated in-memory test session. |
| `tests/test_integration.py` | 64–148 | Add TestClient coverage for successful manual assignments and rejection for TA-cap and department-budget violations; mock HOD lookup and use the fixture database engine. |
| `../app/services/capacity_guard.py` | 1–31 | Restore the CapacityGuard module required by the retained allocation-service refactor after conflict resolution. |
| `../../test_guard.py` | 1–16 | Existing manual capacity guard smoke test; run successfully from the application root. |
