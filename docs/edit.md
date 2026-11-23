# Recently edited

This log was moved from the project root into `docs/`.

| File | Lines | Edit |
| --- | --- | --- |
| `app/main.py` | 6–10, 43–55, 82–87 | Disable public built-in docs and expose Swagger/OpenAPI through admin-protected routes; anonymous requests receive 401 and authenticated non-admins receive 403. |
| `app/seed.py` | 28–43 | Idempotently seed the `admin` account (`admin@example.com`, password `admin`, role `admin`) even when the database already has other users. |
| `app/cli.py` | 58 | Print the seeded admin login after initialization. |
| `app/templates/authenticated-base.html` | 8–40 | Show HOD/admin navigation for Home, Manage Assignments, Review Board, and Admin Overview; expose course management and JSON/API links only to admins. |
| `app/templates/app.html` | 5–22 | Render allocation summary, link HODs to Manage Assignments, and show admin docs/JSON links only to admins. |
| `README.md` | 19–30 | Document admin-only OpenAPI access and the seeded admin account; retain the four-column seeded-accounts table. |
| `tests/test_scenario.py` | 58–95 | Verify docs links are hidden from HODs, anonymous/HOD users cannot access docs or schema, and admins can. |
| `app/services/allocations.py` | 17–24, 68–114 | Import capacity and ranking helpers; retain request validation and TA load calculations; centralize persistence with selected-TA revalidation. |
| `app/services/allocations.py` | 122–159 | Supply TA workloads, prior-experience courses, courses, and department budget to the HOD assignment page. |
| `app/services/allocations.py` | 185–230 | Allow HODs and admins to submit manual assignments through `_persist_assignment`, validating department budget and TA capacity before commit. |
| `app/services/allocations.py` | 232–332 | Validate requests before candidate discovery, filter capacity-ineligible TAs, rank via `get_strategy(mode).rank(...)`, and persist through the shared helper. |
| `app/services/capacity_guard.py` | 1–32 | Keep request-budget validation, TA-cap validation, and capacity-based candidate filtering. |
| `app/services/strategies.py` | 11–101 | Provide experience-first, least-loaded, and round-robin candidate-ranking strategies. |
| `tests/test_strategies.py` | 1–167 | Cover ranking behavior and strategy selection, including unsupported modes. |
| `tests/test_scenario.py` | 97–110 | Verify candidate and review-board views report matching TA capacity values. |
| `app/routers/admin_home.py` | 11–31 | Pass allocation-board data to the admin template and add an authenticated HTML review-board route while preserving the JSON API. |
| `app/routers/user_home.py` | 11–79 | Pass allocation summary data to the home page and allow HODs and admins to access assignment management and form submission routes. |
| `app/templates/admin.html` | 5–73 | Render an overview with TA/course/budget totals and TA workloads, without the assignment list; gate the JSON link to admins. |
| `app/templates/review.html` | 1–21 | Render the detailed review board and expose raw JSON links only to admins. |
| `app/templates/_allocation_board.html` | 2–109 | Render assignment totals, budget, assignment rows, and TA capacity with explicit empty states. |
| `app/templates/manage_allocations.html` | 1–86 | Add the HOD manual-assignment form and TA workload/experience table. |
| `tests/test_scenario.py` | 113–170 | Verify the dashboard overview excludes assignments, HOD pages hide JSON links, admins retain JSON links, and review pages render board data. |
| `tests/test_scenario.py` | 174–225 | Verify HOD assignment-page data, successful manual assignment, and rejection above the TA hour cap. |
| `tests/test_scenario.py` | 236–287 | Verify validation-before-candidate-filtering, selected-TA revalidation before persistence, and capacity-safe auto selection. |
| `tests/test_scenario.py` | 288–399 | Retain strategy-based auto-allocation coverage for ranking, capacity limits, budgets, unsupported modes, and no eligible TAs. |
| `tests/conftest.py` | 21–24 | Add a `db_session` fixture alias for the existing isolated in-memory test session. |
| `tests/test_integration.py` | 64–148 | Add TestClient coverage for successful manual assignments and rejection for TA-cap and department-budget violations; mock HOD lookup and use the fixture database engine. |
| `test_guard.py` | 1–16 | Keep the manual capacity-guard smoke test. |
| `app/routers/admin_home.py` | 41–111 | Add Admin-only course management routes with duplicate-code and invalid-budget handling. |
| `app/templates/manage_courses.html` | 1–60 | Add the course-creation form and existing-course table. |
| `app/routers/register.py` | 15–47 | Collect TA names during signup and pass registration details to the auth service. |
| `app/templates/register.html` | 1–46 | Offer public registration as a regular user or TA, with a name field for TAs; exclude admin and HOD roles. |
| `app/services/auth_service.py` | 21–41 | Restrict public signup to regular users and TAs and require a name for TA registration. |
| `app/repositories/user.py` | 17–94 | Create the TA profile in the same transaction as the user account, using the submitted name and email. |
| `app/models/ta.py` | 12–18 | Add an hourly-rate default of 0.00 and a 0–5 performance rating default of 0 (unrated). |
| `app/database.py` | 42–60 | Add missing TA profile columns to existing databases with defaults during startup. |
| `tests/test_integration.py` | 69–158 | Verify TA signup creates a matching profile with defaults, public signup cannot create privileged users, and legacy databases receive the new columns. |
| `tests/test_scenario.py` | 113–174 | Verify the Admin navigation/course-management page and reject HOD access to course management. |
| `app/templates/authenticated-base.html` | 10–30 | Remove individual JSON links from the top navigation; expose Manage Courses to HODs and admins while keeping the requested admin navigation order. |
| `app/dependencies/auth.py` | 65–77 | Add a course-manager dependency that permits only HODs and admins. |
| `app/routers/admin_home.py` | 49–119 | Allow HODs and admins to view and create courses. |
| `app/routers/admin_home.py` | 121–164 | Add Admin-only course deletion; block courses with assignments and remove unused experience references. |
| `app/templates/manage_courses.html` | 31–69 | Add an admin-only Delete action with a confirmation prompt; keep deletion controls hidden from HODs. |
| `app/routers/admin_home.py` | 167–267 | Add the Admin-only Accounts page, account creation, and role updates; prevent self-demotion and preserve TA profiles/history. |
| `app/services/auth_service.py` | 47–69 | Hash admin-provided initial passwords and validate managed roles and TA profile names. |
| `app/templates/accounts.html` | 1–92 | Add account creation and role-management forms for regular users, TAs, HODs, and admins. |
| `app/templates/admin.html` | 6–12 | Link the Admin overview to the Accounts page without adding another top-navigation item. |
| `tests/test_scenario.py` | 153–335 | Verify navigation, HOD course creation, assignment-protected deletion, admin-only account management, role changes, and TA-history retention. |
| `app/dependencies/auth.py` | 56–63 | Return HTTP 403 for authenticated users without the admin role. |
| `app/routers/admin_home.py` | 34–40 | Restrict the Review Board page to HODs and admins with HTTP 403 for other authenticated roles. |
| `app/routers/user_home.py` | 12–38 | Render a private dashboard for TA/regular-user roles and preserve the global allocation overview for HODs/admins. |
| `app/services/allocations.py` | 121–158 | Return only the current user's TA profile, assigned courses, and weekly hours remaining for the personal dashboard. |
| `app/templates/app.html` | 1–43 | Render TA/regular-user personal data without global metrics or body navigation; retain the HOD/admin overview. |
| `app/templates/authenticated-base.html` | 5–30 | Render only role-appropriate header links in the requested order; remove other page navigation from the body templates. |
| `app/templates/admin.html` | 1–66 | Remove standalone Admin Overview navigation buttons. |
| `app/templates/review.html` | 1–8 | Remove standalone Home/Admin/API navigation links from the Review Board body. |
| `app/templates/_allocation_board.html` | 2–106 | Remove the in-body link to the Review Board. |
| `tests/test_scenario.py` | 403–426 | Verify HOD global overview and header-only navigation. |
| `app/repositories/user.py` | 20–71 | Validate selected course IDs and save TA experience associations atomically with TA account creation; support replacing a TA's selected experience. |
| `app/services/auth_service.py` | 25–83 | Pass optional course experience from public and Admin account creation and reject experience selections for non-TA roles. |
| `app/routers/register.py` | 19–71 | Load available courses for signup and accept experience course IDs with TA registration. |
| `app/routers/admin_home.py` | 177–300 | Supply courses and existing TA experience to account management and persist selected experience for new or promoted TAs. |
| `app/services/allocations.py` | 121–174 | Include a TA's registered prior-experience courses in their personalized dashboard data. |
| `app/templates/register.html` | 1–76 | Add an optional multi-select for prior course experience, enabled for TA registration. |
| `app/templates/accounts.html` | 1–135 | Add optional prior-experience multi-selects for Admin-created and promoted TA accounts. |
| `app/templates/app.html` | 1–56 | Show registered prior course experience alongside the TA/regular-user personal dashboard. |
| `tests/test_scenario.py` | 283–382 | Verify Admin-created TA experience is saved and retained with TA history. |
| `tests/test_scenario.py` | 427–537 | Verify invalid course IDs are rejected and TA/regular-user dashboards show only personal data. |
| `tests/test_scenario.py` | 538–602 | Verify TA/regular-user roles receive 403 for restricted pages and form actions. |
