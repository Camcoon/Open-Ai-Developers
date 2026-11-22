# Strategy Pattern Evidence — Kris

## Implementation

### Strategy Abstraction

- File: `app/services/strategies.py`
- Class: `RankingStrategy`
- Method: `rank(candidates, *, course_id, experience_pairs, load_by_ta)`
- Behavior: Defines the common ranking interface and prevents incomplete Strategy implementations through `ABC` and `abstractmethod`.

### Experience-First Strategy

- File: `app/services/strategies.py`
- Class: `ExperienceFirstStrategy`
- Behavior: Prioritizes prior course experience, then weekly workload, then TA ID.
- Inexperienced candidates remain eligible and appear after experienced candidates.

### Least-Loaded Strategy

- File: `app/services/strategies.py`
- Class: `LeastLoadedStrategy`
- Behavior: Prioritizes lowest weekly workload, then TA ID.
- Prior course experience does not affect ranking.

### Round-Robin Strategy

- File: `app/services/strategies.py`
- Class: `RoundRobinStrategy`
- Behavior: Preserves the existing eligible-candidate order.
- Cursor selection remains in `assign_auto()` rather than inside the ranking class.

### Strategy Registry

- File: `app/services/strategies.py`
- Registry: `STRATEGIES`
- Resolver: `get_strategy(mode)`
- Supported modes:
  - `experience_first`
  - `least_loaded`
  - `round_robin`
- Unsupported modes raise `ValueError` with the supported mode names.

## Design Boundaries

- Strategies receive:
  - eligible candidate dictionaries;
  - course ID;
  - prior TA/course experience pairs;
  - current weekly workload by TA.
- Strategies return:
  - an ordered candidate list for allocation selection.
- Capacity validation is handled by:
  - `app/services/capacity_guard.py`
- Budget validation is handled by:
  - `CapacityGuard.validate_request()` and the allocation service.
- Assignment persistence is handled by:
  - `assign_manual()` and `assign_auto()` in `app/services/allocations.py`.
- HOD authorization is handled by:
  - `app/services/allocation_auth.py` and the allocation service.

## Tests

- Strategy test file: `tests/test_strategies.py`
- Strategy unit test result: 15 passed
- Allocation/API integration result: 26 passed
- Complete suite result: 48 passed
- Failures: 0
- Unit command:

```powershell
python -m pytest tests/test_strategies.py -q
```

- Full command:

```powershell
python -m pytest tests -q
```

- Evidence date: 2026-11-22
- Final implementation commit: `59a9d9f`
- Final integration commit subject:
  `Complete Strategy pattern teammate integration`

## Integration

### Jordan — CapacityGuard

- Implemented `CapacityGuard.validate_request()`.
- Implemented `CapacityGuard.validate_ta()`.
- Implemented `CapacityGuard.eligible_candidates()`.
- The guard removes TAs whose projected weekly workload would exceed 20 hours.
- Department budget is checked before candidate ranking.

### Cameron — Allocation integration

- `assign_auto()` validates the mode.
- `assign_auto()` validates positive hours and department budget.
- `assign_auto()` obtains eligible candidates from `CapacityGuard`.
- `assign_auto()` calls `get_strategy(mode).rank(...)` directly.
- The selected TA is revalidated before persistence.
- Assignment and department budget changes are committed or rolled back together.
- The temporary `auto_select_ta()` compatibility wrapper was removed.

### Experience-First Result

- Experienced eligible candidates rank first.
- Workload breaks ties within experience groups.
- Inexperienced candidates remain in the ranked list.
- Integration tests passed.

### Least-Loaded Result

- Eligible candidates rank by lowest workload.
- TA ID provides deterministic tie-breaking.
- Experience does not affect ranking.
- Integration tests passed.

### Round-Robin Result

- Eligible candidates preserve their existing stable order.
- `assign_auto()` uses `_RR_CURSOR` to select the next candidate.
- Over-capacity candidates are removed before ranking.
- Unit and integration tests passed.

## Class and Dependency Diagram

```text
CapacityGuard
  + validate_request(...)
  + validate_ta(...)
  + eligible_candidates(...)

assign_auto() / allocation service
  + validates HOD and request
  + calls CapacityGuard
  + calls get_strategy(mode)
  + ranks eligible candidates
  + persists Assignment

RankingStrategy (ABC)
  + rank(...)
        ^
        |
        +---------------+---------------+
        |               |               |
ExperienceFirstStrategy LeastLoadedStrategy RoundRobinStrategy

STRATEGIES
  experience_first -> ExperienceFirstStrategy
  least_loaded -> LeastLoadedStrategy
  round_robin -> RoundRobinStrategy

get_strategy(mode) -> RankingStrategy
```

`CapacityGuard` is separate from `RankingStrategy`; it owns hard eligibility
and does not inherit from or depend on a ranking implementation.

## GitHub and Handoff

- Kris implementation branch: `feature/12-ranking-strategies`
- Final implementation commit: `59a9d9f`
- Pull request: pending teammate review and merge
- Reviewer: pending
- Merge commit: pending
- Final PR link:
  `https://github.com/Camcoon/Open-Ai-Developers/pull/new/feature/12-ranking-strategies`

### Handoff to Cameron

Import and use the Strategy resolver:

```python
from app.services.strategies import get_strategy

strategy = get_strategy(mode)

ranked_candidates = strategy.rank(
    eligible_candidates,
    course_id=course_id,
    experience_pairs=experience_pairs,
    load_by_ta=load_by_ta,
)

selected_ta = ranked_candidates[0] if ranked_candidates else None
```

Supported modes:

- `experience_first`
- `least_loaded`
- `round_robin`

The allocation service must pass only eligible candidates. Strategy classes
do not validate 20-hour capacity, department budget, HOD authorization, or
persistence.

### Handoff to Jordan

`CapacityGuard.eligible_candidates()` supplies the candidate list passed to
`rank()`. Candidates with `current_load + requested_hours <= 20` remain
eligible. No Strategy may restore a removed candidate or become responsible
for the hard cap.

## Remaining Issues

- GitHub review and merge are pending because the branch has not yet been merged by the team.
- A PR reviewer and merge commit cannot be recorded until review completes.
- The project has no Strategy evidence screenshots; text test evidence is sufficient for the current repository handoff.
- FastAPI and Starlette emit deprecation warnings, but no tests fail.
