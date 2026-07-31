# Shui implementation and wiring audit

Unified entry: **True**
Production files: **51**
Test files: **22**

| Module | Implementations | Test refs | Production refs |
|---|---:|---:|---:|
| identity | 1 | 1 | 1 |
| values | 1 | 4 | 5 |
| goals | 1 | 4 | 3 |
| contracts | 1 | 3 | 7 |
| perception | 6 | 3 | 3 |
| provenance | 1 | 1 | 1 |
| world_model | 1 | 1 | 2 |
| attention | 1 | 1 | 0 |
| cognition | 4 | 4 | 1 |
| capabilities | 1 | 1 | 2 |
| experiments | 2 | 2 | 0 |
| execution | 1 | 2 | 2 |
| feedback | 0 | 0 | 0 |
| learning | 1 | 2 | 1 |
| evolution | 1 | 2 | 1 |
| audit | 3 | 5 | 4 |
| recovery | 1 | 1 | 1 |

## Phase 11 verified risks

1. `feedback/` remains empty; verified outcomes live in `learning/` but no user-feedback adapter exists.
2. `AuditChain.append` performs read-verify-append without an inter-process lock; concurrent writers can select the same previous hash.
3. CLI behavior is unit-tested in-process; no subprocess test currently proves real exit codes and filesystem side effects.
4. HTTP is the only production network protocol; RSS/Atom and paper metadata adapters are absent.
5. No provider-neutral model protocol or model adapter exists; current cognition remains deterministic only.
6. Candidate capabilities use `python -I`, but inherit the parent environment and operating-system authority.
7. WorldModel supports storage and trace-by-ID internally, but has no filter/search/explain API or CLI commands.
8. The configured capability timeout is not wired into `CapabilityEvolution`, which still contains a fixed process timeout.
9. The completed soak gate is six cycles, not an hour/day certification.

## Risk-ordered implementation

Concurrent audit integrity → subprocess CLI proof → capability timeout/isolation → query interface → source portfolio → model protocol → timed certification.
