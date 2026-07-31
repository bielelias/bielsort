# Security Policy

## Supported versions

Only the latest patch release in the `0.1.x` series receives security fixes.
Pre-releases and older source snapshots are not supported.

| Version | Supported |
|---|---|
| Latest `0.1.x` | Yes |
| `< 0.1` | No |

## Reporting a vulnerability

Do not open a public issue for memory-safety bugs, crashes with crafted input,
reference-count corruption, or build/release credential problems.

Use GitHub's private vulnerability reporting from the repository's Security
page. If that form is unavailable, contact Gabriel Fernandes Farah Elias at
`gabriel_elias@msn.com` with the subject `BielSort security report`.

Include:

- operating system, architecture, and Python version;
- a minimal reproducer;
- whether the issue affects new-list or in-place sorting;
- sanitizer or crash output, if available;
- potential impact.

Do not include secrets or sensitive production data in the report. The
maintainer will acknowledge the report as soon as practical, investigate it
privately, and coordinate disclosure after a fix or mitigation is available.
