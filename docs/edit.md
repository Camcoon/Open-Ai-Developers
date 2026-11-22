# Recently edited

This log was moved from the project root into `docs/`.

| File | Lines | Edit |
| --- | --- | --- |
| `app/main.py` | 6, 13, 41–52 | Added Swagger UI and OpenAPI schema routes protected by `AdminDep`; disabled FastAPI's public built-in docs remains in effect. |
| `app/main.py` | 80–87 | Return the existing unauthorized page with HTTP 401 so denied docs requests are not reported as successful. |
| `app/seed.py` | 28–42 | Idempotently seed the `admin` account (`admin@example.com`, password `admin`, role `admin`) even when the database already has other users. |
| `app/cli.py` | 58 | Print the seeded admin login after initialization. |
| `app/templates/app.html` | 11–14 | Display the OpenAPI docs link on the user home page only for admins. |
| `README.md` | 19–30 | Document admin-only OpenAPI access and the seeded admin account. |
| `tests/test_scenario.py` | 35–73 | Verify docs links are hidden from HODs, anonymous/HOD users cannot access docs or schema, and admins can. |
| `app/services/allocations.py` | 17, 113–220 | Apply request budget checks before auto candidate filtering; filter TAs by capacity; revalidate the selected TA and request before assignment persistence. |
| `app/services/allocations.py` | 65–112, 222–246 | Extract shared request-error and TA capacity calculations for assignment and candidate/review views. |
| `tests/test_scenario.py` | 75–89 | Verify candidate and review-board views report matching TA capacity values. |
| `tests/test_scenario.py` | 92–153 | Cover validation-before-candidate-filtering, selected-TA revalidation before persistence, and capacity-safe auto selection. |
| `../app/services/capacity_guard.py` | 6–43 | Existing guard implementation used by the allocation service for request, TA, and candidate capacity checks; this file was not changed in this task. |
| `../../test_guard.py` | 1–16 | Existing manual capacity guard smoke test; run successfully from the application root. |
