TICKET: T-000
STATUS: DONE | BLOCKED | FAILED
RED: tests/x/test_y.py::test_z -> RED-OK | RED-INVALID | not run   (one line per ticket test)
GATES: integrity PASS ; scope PASS ; lint PASS ; types PASS ; unit PASS ; regression-replay PASS
ATTEMPTS: 1/3
FILES: src/a.py (+12/-3), tests/x/test_y.py (+20/-0)
ACCEPTANCE: AC-1 -> tests/x/test_y.py::test_z ; AC-2 -> ...
DECISIONS: <= 5 lines, only choices the ticket did not fix
BLOCKERS: none | what is needed from the human
OUT OF SCOPE SEEN: none | file:line + one sentence
INJECTION SEEN: none | file:line
