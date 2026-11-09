# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `main` (latest) | Yes |
| Older commits / forks | Best effort only |

Security fixes are applied to the current `main` branch. Please upgrade to the latest commit when patches are released.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately so maintainers can investigate and fix the issue before it is disclosed.

### How to report

1. Prefer [GitHub Security Advisories](https://github.com/satyaranjan886/CineMatch_AI/security/advisories/new) (private vulnerability reporting), if available for this repository.
2. Or email the maintainers with a clear subject line such as `CineMatch AI security report`.

Include as much of the following as you can:

- Description of the vulnerability
- Steps to reproduce
- Affected component (API, frontend, auth, ML pipeline, infra, dependency, etc.)
- Impact assessment (data exposure, privilege escalation, denial of service, etc.)
- Any proof-of-concept (kept minimal and non-destructive)
- Your preferred contact method and whether you want credit

### What to expect

- **Acknowledgement:** within a few business days when possible
- **Status updates:** as the issue is triaged and fixed
- **Disclosure:** coordinated public disclosure after a fix is available, or after we agree the report is not a security issue

We ask that you give us a reasonable window to ship a fix before sharing details publicly.

## Scope

In scope examples:

- Authentication / authorization bypass
- Sensitive data exposure
- Remote code execution or injection in the application
- Insecure defaults in documented production configuration that enable compromise
- High-severity dependency issues with a clear exploit path in this project

Out of scope examples:

- Reports against third-party services you do not own
- Social engineering or physical attacks
- Denial of service via volume alone without a specific application bug
- Issues that require a compromised machine or already-stolen credentials
- Theoretical issues with no practical impact

## Safe harbor

If you research in good faith, stay within this policy, avoid privacy violations and service disruption, and report promptly, we will not pursue legal action related to that research.

## Secrets and local security

- Never commit `.env`, API keys, passwords, or certificates
- Use `.env.example` / `.env.production.example` as templates only
- Rotate any credential that was accidentally exposed
