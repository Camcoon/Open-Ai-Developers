# Kris Strategy Pattern — Sprint 2 Documentation

## 1. Purpose

This document records the analysis and design completed for Kris's Strategy
pattern responsibilities in Sprint 2. It covers Phase 2 and provides the
temporary integration agreement used while teammates develop and merge their
parts independently.

Phase 1 is considered temporarily complete. The interfaces and boundaries may
be revised after teammate integration is available.

## 2. Responsibility Boundary

Kris is responsible for ranking already eligible Teaching Assistant candidates.
The system will use the following separation of responsibilities:

```text
All TAs
  |
  v
CapacityGuard / eligibility validation
  |
  v
Eligible TA candidates
  |
  v
Ranking strategy
  |
  v
Ranked candidates, from most preferred to least preferred
```

The Strategy classes must not:

- connect to the database;
- create or update assignments;
- enforce the 20-hour weekly TA limit;
- validate or change the departmental budget;
- authenticate the HOD;
- return HTTP responses;
- filter inexperienced candidates from experience-first ranking.

Jordan owns eligibility and hard-rule validation. Cameron owns allocation
integration and assignment persistence.

## 3. Project and Domain Findings

The relevant domain models are represented as follows:

| Model | Relevant fields |
|---|---|
| `Ta` | `id`, `name`, `email` |
| `Course` | `id`, `code`, `title`, `budgeted_hours` |
| `Assignment` | `ta_id`, `course_id`, `weekly_hours`, `created_at` |
| `TaExperience` | `ta_id`, `course_id` |

`TaExperience` records prior course experience. A pair is represented as:

```python
(ta_id, course_id)
```

For example, `(3, 10)` means TA 3 has prior experience with course 10.

This is converted into a set named `experience_pairs` and supplied to ranking
strategies. The Strategy classes should not execute database queries to obtain
this information.

## 4. Candidate Representation

The temporary candidate representation is a dictionary:

```python
candidate = {
    "id": 1,
    "name": "Example TA",
    "email": "ta@example.com",
}
```

The ranking interface identifies candidates with the `id` key. Candidate
dictionaries may contain additional fields, but ranking code must not require
fields beyond `id` in the sorting key.

This representation aligns with the existing `model_dump()` data used by
[allocations.py](/Users/User/Open-Ai-Developers/app/services/allocations.py).
It may be adapted later if Cameron and Jordan standardize on SQLModel objects,
but it should not mix dictionary and object access in one Strategy
implementation.

## 5. Weekly Workload Representation

Current weekly workload is represented separately as:

```python
load_by_ta = {
    1: 18,
    2: 5,
    3: 12,
}
```

This map contains:

- existing assignment hours for the TA in the current week;
- workload across active assignments;
- only the TA's current planned weekly hours.

It does not contain:

- semester workload;
- lifetime workload;
- remaining departmental budget;
- the requested hours for the new assignment.

The Strategy reads `load_by_ta.get(ta_id, 0)`. Missing values mean a
zero-hour workload assumption.

The hard 20-hour check belongs to the eligibility phase and must confirm:

```text
current weekly workload + requested assignment hours <= 20
```

## 6. Ranking Rules

### 6.1 Experience-First Strategy

Ranking priority:

1. TAs with prior experience in the requested course.
2. Lower weekly workload among experienced candidates.
3. Lower weekly workload among inexperienced candidates.
4. Lower TA ID as a final deterministic tie-break.

The sort key is conceptually:

```python
(
    has_no_experience,
    weekly_workload,
    ta_id,
)
```

Experience is a soft preference. Inexperienced candidates remain eligible and
must appear after experienced candidates rather than being removed.

### 6.2 Least-Loaded Strategy

Ranking priority:

1. Lowest weekly workload.
2. Lower TA ID as a final deterministic tie-break.

Prior course experience is ignored by this Strategy.

### 6.3 Tie-breaking

When all higher-priority ranking values are equal, lower TA ID wins. This makes
ordering deterministic and testable.

## 7. Supported and Unsupported Modes

The supported Strategy modes are initially:

```text
experience_first
least_loaded
```

`round_robin` exists in the flawed starter implementation, but it is not
included in Kris's required Strategy design unless the team explicitly
implements and tests it. This is an assumption under independent development.

Any unsupported mode must raise an explicit error. It must not silently select
a first candidate or a default Strategy.

## 8. Proper Strategy Class Design

```text
RankingStrategy (abstract)
├── rank(candidates, course_id, experience_pairs, load_by_ta)
├── ExperienceFirstStrategy
│   └── rank(candidates, course_id, experience_pairs, load_by_ta)
└── LeastLoadedStrategy
    └── rank(candidates, course_id, experience_pairs, load_by_ta)

STRATEGIES: mode name -> RankingStrategy instance
get_strategy(mode): RankingStrategy
```

### 8.1 `RankingStrategy`

Defines the common Strategy interface:

```python
rank(
    candidates,
    *,
    course_id,
    experience_pairs,
    load_by_ta,
) -> ranked_candidates
```

It is abstract so an incomplete ranking implementation cannot be used as a
substitute Strategy.

### 8.2 `ExperienceFirstStrategy`

Returns every eligible candidate in ranked order, placing candidates with prior
experience for the course first. It does not remove inexperienced candidates.

### 8.3 `LeastLoadedStrategy`

Returns every eligible candidate in ranked order, placing the TA with the
lowest current weekly workload first. It does not use experience in its sort
key.

### 8.4 `STRATEGIES`

Maps supported public mode names to Strategy instances:

```text
"experience_first" -> ExperienceFirstStrategy
"least_loaded"    -> LeastLoadedStrategy
```

The registry removes mode-switching logic from the allocation service.

### 8.5 `get_strategy()`

Accepts a mode name and returns the matching Strategy. An unknown mode raises
`ValueError` and includes the supported mode names in the error message.

## 9. Service Integration Contract

The expected allocation-service workflow is:

```text
1. Validate the allocation request and HOD authorization.
2. Validate that the requested hours are positive.
3. Obtain the course and eligible TAs.
4. Calculate each candidate's current weekly workload.
5. Obtain prior TA/course experience pairs.
6. Check hard eligibility and departmental budget.
7. Call get_strategy(mode).
8. Call strategy.rank(eligible_candidates, ...).
9. Select the first ranked candidate.
10. Persist the assignment.
```

The temporary agreed `rank()` inputs are:

| Parameter | Type | Purpose |
|---|---|---|
| `candidates` | `list[dict[str, Any]]` | Eligible candidates only |
| `course_id` | `int` | Course used to identify prior experience |
| `experience_pairs` | `set[tuple[int, int]]` | Prior TA/course experience |
| `load_by_ta` | `dict[int, int]` | Existing weekly workloads |

The temporary expected return type is `list[dict[str, Any]]`, ordered from most
preferred to least preferred.

The allocation service handles an empty ranked list and unknown modes. Strategies
should rank a valid empty list safely and return an empty list when appropriate.

## 10. Existing Implementation Findings

The current [strategies.py](/Users/User/Open-Ai-Developers/app/services/strategies.py)
contains one nested conditional function. It has the following defects:

- experience-first hard-filters candidates instead of using experience as
  preference;
- least-loaded does not receive eligibility filtering;
- round-robin may select a TA with insufficient capacity;
- budget handling is inconsistent;
- unknown modes silently fall back to the first candidate;
- Strategy ranking is combined with hard validation and selection.

These findings identify the code that Kris's implementation should replace or
adapt, with preserving current function compatibility coordinated through
Cameron.

The current [allocations.py](/Users/User/Open-Ai-Developers/app/services/allocations.py)
uses `model_dump()` to produce dictionaries and retrieves workloads, experience,
and budget in the service layer. This supports the temporary dictionary
representation.

## 11. Assumptions and Deferred Decisions

The following assumptions are in effect during independent development:

1. Candidate dictionaries use `id` as the TA identifier.
2. `load_by_ta` contains current planned weekly assignment hours.
3. `experience_pairs` contains `(ta_id, course_id)` pairs.
4. Both ranking strategies receive only candidates already eligible under
   Jordan's hard rules.
5. Experience-first does not exclude inexperienced candidates.
6. Least-loaded ignores experience.
7. Lower TA ID is the deterministic tie-break.
8. `experience_first` and `least_loaded` are the only required modes for Kris's
   part.
9. The allocation service will resolve a Strategy through `get_strategy()`.
10. Existing dictionary and function names may remain temporarily, but final
    integration should move selection away from nested mode conditionals.

These assumptions are temporary. Jordan's exact `CapacityGuard` signature and
Cameron's exact allocation integration signature may require small changes
during merge.

## 12. Phase 4 — Strategy Selection Handoff

### 12.1 Confirmed import and resolver

Cameron's allocation service should import Strategy selection through:

```python
from app.services.strategies import get_strategy
```

The `get_strategy(mode)` resolver is the only central mode-to-Strategy lookup.
The allocation service should not contain `if/elif` statements for
`experience_first`, `least_loaded`, or other ranking modes.

The two supported mode values are:

```text
experience_first
least_loaded
```

An unsupported mode raises `ValueError`:

```text
Unsupported allocation mode: <mode>. Supported modes: experience_first, least_loaded
```

The active allocation service now validates this resolver result before
continuing. Returning the error as the existing service's payload format
prevents unknown modes from reaching candidate selection or persistence.

### 12.2 Intended Cameron integration call

Cameron should select the policy after all request validation and eligibility
work is complete:

```python
strategy = get_strategy(mode)

ranked_candidates = strategy.rank(
    eligible_candidates,
    course_id=course_id,
    experience_pairs=experience_pairs,
    load_by_ta=load_by_ta,
)

selected_ta = ranked_candidates[0] if ranked_candidates else None
```

The service may use a different local variable name, but the method call,
keyword arguments, and ordered-list result must remain compatible.

### 12.3 Selection sequence

Cameron's intended final sequence is:

```text
1. Validate HOD authorization.
2. Validate positive requested hours.
3. Load the course.
4. Load all TA candidates.
5. Calculate current weekly workloads.
6. Load prior TA/course experience pairs.
7. Check department budget.
8. Apply Jordan's CapacityGuard.
9. Resolve get_strategy(mode).
10. Rank eligible_candidates.
11. Select ranked_candidates[0], or return no-candidate output.
12. Persist through the allocation repository/service.
```

Kris's code must not be used to perform steps 1-8 or 12.

### 12.4 Empty candidate behavior

When an eligible candidate list is empty, Cameron's service must handle the
empty result explicitly. Expected behavior is an allocation failure or
`no eligible TAs` result; it must not persist an assignment or silently select
a TA.

The ranking Strategies themselves safely return an empty list when passed an
empty candidate list because `sorted([], ...)` is empty.

### 12.5 Capacity and budget separation

The permanent integration must keep hard constraints outside `rank()`:

- Jordan's eligibility logic adds only TAs whose projected weekly hours are
  at or below 20.
- Cameron's allocation service validates department budget before ranking.
- `rank()` uses only eligible candidates and ranking preference data.
- Ranking must never mutate the candidate list or assignment database.

The temporary `auto_select_ta()` compatibility wrapper in
`app/services/strategies.py` currently applies extra starter-service checks
because it still bridges the pre-Strategy implementation. It must be removed
or stopped from owning eligibility once Cameron and Jordan complete their
integration. Cameron should call `get_strategy(mode).rank(...)` directly in the
final allocation service.

### 12.6 Integration handoff decision

The candidate representation remains:

```python
list[dict[str, Any]]
```

The Strategy input and return contract remains:

```python
rank(
    candidates,
    *,
    course_id,
    experience_pairs,
    load_by_ta,
) -> list[dict[str, Any]]
```

Before merge, Cameron and Jordan should notify Kris of any of these changes:

- SQLModel candidate objects instead of dictionaries;
- a new workload field or workload source;
- a new eligibility/CapacityGuard function name;
- a different empty-candidate response shape;
- persistence API changes.

If the candidate representation changes, Cameron and Kris should update both
Strategy key access and tests together. Kris must not add duplicate database
queries or eligibility logic as a workaround.

## 13. Duplicate Logic Review

The active `assign_auto()` path previously contained no separate ranking
algorithm, but used a compatibility `auto_select_ta()` function and a no-op
unknown-mode block.

The no-op block has been replaced with `get_strategy(mode)` validation.
The compatibility wrapper is temporary and delegates its candidate ordering to
the registered Strategy classes.

Final integration should remove `auto_select_ta()` and ensure the service
passes the already eligible candidate list directly to
`get_strategy(mode).rank(...)`.

## 14. Phase 2 Completion Criteria

- [x] Existing Strategy implementation inspected.
- [x] Existing allocation service inspected.
- [x] TA, course, assignment, and experience fields understood.
- [x] Prior experience representation confirmed.
- [x] Weekly workload representation confirmed.
- [x] Class responsibilities and boundaries finalized.
- [x] Ranking rules and tie-breaking documented.
- [x] Temporary teammate integration contract documented.

## 15. Phase 5 — Unit Test Handoff

Phase 5 uses pure unit tests in
`tests/test_strategies.py`. These tests do not initialize or query the
database.

### 15.1 Covered behavior

The test suite verifies:

- experienced candidates rank before inexperienced candidates;
- experienced candidates are ranked by lowest workload;
- inexperienced candidates are not removed;
- experience-first falls back to workload when nobody has experience;
- least-loaded ignores experience;
- lower TA ID wins equal ranking values;
- empty candidate lists return empty lists;
- both supported modes resolve to the correct Strategy class;
- unknown modes raise `ValueError`;
- ranking does not mutate the original candidate list.

### 15.2 Testing assumptions

Tests use dictionaries containing `id` because that is the temporary candidate
representation. They pass workload and experience data as separate arguments.
No test performs database, persistence, authentication, budget, or
CapacityGuard work.

If Cameron and Jordan change the candidate representation or ranking function
arguments, update these tests in the same integration change. Test fixtures
should change only where the public contract changes.

### 15.3 Integration test boundaries

The following remain teammate-owned integration concerns:

- department budget validation;
- 20-hour weekly capacity validation;
- assignment persistence;
- HOD authorization;
- end-to-end HTTP behavior.

The Strategy unit tests prove ranking behavior but do not replace integration
tests. Cameron and Jordan should add end-to-end tests after their components
merge.

### 15.4 Phase 5 Validation

Run:

```powershell
python -m pytest tests/test_strategies.py -v
python -m pytest tests -v
```
