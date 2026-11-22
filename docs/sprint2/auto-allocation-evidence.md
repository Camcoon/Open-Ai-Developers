# Phase 5 Automatic Allocation Evidence

**Date:** 2026-11-21

**Branch:** `feature/15-auto-allocation`

## Focused Results

- Strategy and isolated service tests:
  `python -m pytest tests/test_strategies.py tests/test_auto_allocation.py -q`
  - **23 passed**
- API scenario tests:
  `python -m pytest tests/test_scenario.py -q`
  - **15 passed, 7 warnings**
- Full suite:
  `python -m pytest tests -q`
  - **45 passed, 7 warnings**

## Coverage

No coverage configuration or `pytest-cov` dependency is present. Coverage was not run.

## Startup Verification

Command:

```powershell
python manage.py run
```

The server reached application startup on `http://127.0.0.1:5000`.

Health probe:

```text
Invoke-RestMethod -Uri http://127.0.0.1:5000/health -Method Get
```

Response:

```json
{"ok":true,"status":"ok","scenario":"ta-allocations","version":"0.2.0"}
```

## Verified Behavior

- Experience-first ranking is covered.
- Least-loaded ranking is covered.
- The 18 + 2 hour cap boundary is allowed.
- The 18 + 3 hour boundary excludes the over-cap TA.
- Insufficient department budget is rejected without changing assignments or budget.
- Unknown strategies are rejected.
- Zero and negative hours are rejected without state change.
- No eligible candidate returns an error without state change.
- Successful API allocation creates one persisted assignment and deducts budget hours.
- Persistence failure coverage verifies assignment and budget rollback.

## Remaining Limitation

The implementation does not add row locking or an atomic conditional update for concurrent requests. Concurrency safety is not claimed.

## Screenshot Instructions

No screenshots were captured. Cameron can create the following genuine evidence in `docs/sprint2/screenshots/`:

1. Open `http://127.0.0.1:5000/docs` as an HOD and capture the automatic-allocation endpoint.
2. Submit `experience_first` with weekly hours within the remaining capacity and capture the successful response.
3. Submit `least_loaded` and capture the successful response.
4. Submit 3 weekly hours for the seeded TA already at 18 hours and capture the rejection/eligible-TA result.
5. Submit a request exceeding the department budget and capture the 400 response.
6. Open `/api/assignments` and `/api/review` afterward and capture unchanged state for a failed request.
