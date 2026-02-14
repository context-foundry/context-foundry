# Workday Extend Extension

## Overview

This extension covers **Workday Extend** application development -- the PaaS platform for building custom apps that run natively inside Workday tenants.

## Key Files

| File | Contents |
|------|----------|
| `WORKDAY_EXTEND_DEVELOPER_GUIDE.md` | Practical development workflow: environment setup, app lifecycle, testing, troubleshooting, deployment, APIs, advanced patterns |
| `WORKDAY_EXTEND_ARCHITECTURE.md` | Core architecture: platform layers, business objects, metadata structures, Canvas design system |
| `orchestrations-integrations-guide.md` | Deep dive on orchestrations, integration patterns, and business process automation |
| `security-reporting-birt-notes.md` | Workday security model, reporting engine, BIRT templates, Prism Analytics, audit/compliance |
| `LATEST_DEVELOPMENTS.md` | Latest platform changes: Workday Build, DevCon 2024/2025 announcements, AI features, Visual UI Mode |
| `patterns/extend-common-issues.json` | Learned patterns and common issues (machine-readable) |

## Before Starting Extend Work

1. Read `WORKDAY_EXTEND_DEVELOPER_GUIDE.md` for practical workflow guidance
2. Read `WORKDAY_EXTEND_ARCHITECTURE.md` for core architecture understanding
3. Read the domain-specific guide relevant to your task:
   - Orchestrations/integrations: `orchestrations-integrations-guide.md`
   - Security/reporting: `security-reporting-birt-notes.md`
4. Read `patterns/extend-common-issues.json` for known issues and solutions
5. Read global patterns: `mcp__context-foundry__read_global_patterns("common-issues")`

## Critical Rules

- **No local file-based development**: Extend apps are built entirely in the browser-based App Builder
- **Security policy activation is mandatory**: After ANY security change, run "Activate Pending Security Policy Changes"
- **Credentials never migrate**: Always re-enter integration credentials after deploying to a new tenant
- **WIDs are tenant-specific**: Never hardcode WIDs; use Reference IDs or configuration business objects
- **CORS requires configuration**: Workday REST APIs require explicit CORS origin configuration in the API client; browser calls fail without it. Extend apps use orchestration steps instead of direct browser calls. ([source: extend-js-example](https://github.com/Workday/extend-js-example))
- **Extend requires a license**: Not all Workday customers have Extend access
- **Test before every release**: Workday releases twice per year and can break Extend apps

## Common Tasks

| Task | File | Section |
|------|------|---------|
| Start new Extend app | Developer Guide | Section 2.2 |
| Create business objects | Developer Guide | Section 2.4 |
| Build UI pages | Developer Guide | Section 2.5 |
| Write WEL expressions | Developer Guide | Section 2.8 |
| Set up orchestrations | Developer Guide | Section 2.9 (overview), Orchestrations Guide (deep dive) |
| Create custom APIs | Developer Guide | Section 2.10 |
| Deploy between tenants | Developer Guide | Section 5.2-5.3 |
| Debug orchestrations | Developer Guide | Section 4.1 |
| Set up OAuth 2.0 | Developer Guide | Section 6.8 |
| Configure security | Security Guide | Sections 1.1-1.8 |
| Build reports | Security Guide | Reporting sections |
| Architecture decisions | Architecture Guide | All sections |
| Integration patterns | Orchestrations Guide | Integration sections |

## After Solving Issues

When you solve a new Workday Extend problem:

1. Add to `patterns/extend-common-issues.json`
2. Merge to global: `mcp__context-foundry__merge_project_patterns("<path>/patterns/extend-common-issues.json", "common-issues")`
