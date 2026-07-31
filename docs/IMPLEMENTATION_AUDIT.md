# Shui implementation and wiring audit

Unified entry: **False**
Production files: **39**
Test files: **13**

| Module | Implementations | Test refs | Production refs |
|---|---:|---:|---:|
| identity | 1 | 1 | 0 |
| values | 1 | 2 | 2 |
| goals | 1 | 2 | 1 |
| contracts | 1 | 3 | 5 |
| perception | 6 | 3 | 2 |
| provenance | 1 | 1 | 1 |
| world_model | 1 | 1 | 1 |
| attention | 1 | 1 | 0 |
| cognition | 2 | 2 | 0 |
| capabilities | 1 | 1 | 2 |
| experiments | 0 | 0 | 0 |
| execution | 1 | 1 | 1 |
| feedback | 0 | 0 | 0 |
| learning | 1 | 1 | 0 |
| evolution | 1 | 1 | 0 |
| audit | 1 | 1 | 0 |
| recovery | 0 | 0 | 0 |
## Verified gaps

1. No unified `shui.py` entry exists.
2. `experiments`, `feedback`, and `recovery` have no implementation files.
3. Identity, attention, learning, evolution, and audit are tested but have no production caller outside their own module.
4. The autonomous loop consumes local files; HTTP observations are not yet converted into its Evidence-to-Verification chain.
5. Learning outcomes are not yet written by the autonomous loop or used by its next goal selection.
6. Configuration has no implementation and the runtime cannot yet start from validated external configuration.
7. There is no heartbeat, checkpoint coordinator, daemon loop, or measured long-duration run.

## Productionization order derived from gaps

Configuration → audit chain → unified entry → HTTP loop integration → learning integration → heartbeat/recovery → fault matrix → sustained run.
