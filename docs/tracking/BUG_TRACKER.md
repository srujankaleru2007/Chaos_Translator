# Bug tracker

## Remediation status — 2026-10-04

| ID | Status | Severity | Finding |
|---|---|---|---|
| BUG-001 | Fixed in code/config; live tags verified | High | E4B/E2B defaults are aligned. |
| BUG-002 | Fixed | High/Medium | Frontend uses one JSON `/api/v1/inference/test` client. |
| BUG-003 | In progress | Medium | Legacy frontend components still produce 29 lint errors. |
| BUG-004 | Fixed | Medium | Blank and 30,000-character validation exists client and server side. |
| BUG-005 | Fixed | Medium | Provider failures are categorized and 503 details are sanitized. |
| BUG-006 | Fixed | Medium | Remote Google Font dependency removed from layout. |

Remaining blockers: legacy lint errors, Windows Next.js `spawn EPERM`, and missing production auth/isolation.
