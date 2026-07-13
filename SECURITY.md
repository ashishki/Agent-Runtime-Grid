# Security policy

## Supported scope

Security fixes are accepted for the current `0.1.x` development line. This is a
local-first alpha and is not supported as an internet-facing hosted service.

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting or security-advisory flow for this
repository. Do not publish secrets, exploit payloads, private data, or a working
attack in a public issue.

Include the affected revision, a minimal reproduction, expected impact, and any
safe mitigation already tested. Reports about third-party services should also
follow that provider's disclosure process.

## Boundaries

- Compose binds Postgres and Redis to loopback and uses development credentials.
- Proof commands refuse destructive reset for remote or unrelated databases and
  require an explicit local-reset flag.
- Arbitrary untrusted job execution is not a supported use case.
- Stub mode is the default evidence path; live provider use requires explicit
  secrets and cost limits outside committed files.

See `docs/SECURITY_BOUNDARIES.md` and `docs/KNOWN_LIMITS.md` before deployment.
