# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.4.x   | :white_check_mark: |
| 2.3.x   | :white_check_mark: |
| < 2.3   | :x:                |

## Security Model

Context Foundry runs **entirely on your local machine**. No data is sent to external servers beyond the Claude API calls you explicitly make.

**Key points:**
- Spawned Claude instances inherit your local permissions
- Code execution happens in your environment with your credentials
- GitHub deployments use your configured authentication

## Reporting a Vulnerability

Report security issues via [GitHub Security Advisories](https://github.com/context-foundry/context-foundry/security/advisories/new).

We aim to respond within 48 hours and will work with you to understand and address the issue before any public disclosure.
