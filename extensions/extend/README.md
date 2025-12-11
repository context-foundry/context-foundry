# Workday Extend Extension for Context Foundry

A comprehensive extension that teaches Claude Code how to build production-quality Workday Extend applications.

## Features

- **Complete PMD Documentation** - Expression syntax, 50+ widgets, event handlers
- **42 Quality Rules** - Based on ArcaneAuditor for production-ready code
- **20 Example Files** - Real PMD patterns you can copy
- **Test Validation Checklist** - For automated quality checks

## Installation

### Option 1: Clone into Context Foundry (Recommended)

```bash
# Navigate to your Context Foundry installation
cd /path/to/context-foundry/extensions

# Clone this extension
git clone https://github.com/YOUR_ORG/workday-extend-extension.git extend

# That's it! The extension is now available
```

### Option 2: Manual Download

1. Download this repository as a ZIP
2. Extract to `context-foundry/extensions/extend/`
3. Ensure the folder structure matches:

```
context-foundry/
  extensions/
    extend/
      CLAUDE.md          <- Entry point
      docs/
      examples/
      patterns/
      tests/
```

## Usage

### Building Extend Apps with Context Foundry

When you ask Claude Code to build a Workday Extend app, it will automatically:

1. Read `CLAUDE.md` for PMD syntax and patterns
2. Follow the 42 quality rules in `docs/QUALITY-RULES.md`
3. Use examples from `examples/` as templates
4. Avoid common issues listed in `patterns/extend-common-issues.json`

### Example Prompts

```
"Build a Workday Extend app that displays a list of workers with search"

"Create an Extend page with a form that calls a REST API"

"Build a multi-page flow with survey and results pages"
```

### For Test Agent

The Test agent uses `tests/extend-quality-checklist.json` to validate built apps against all 42 rules.

## File Structure

```
extend/
├── CLAUDE.md                    # Entry point - always read first
├── RESUME.md                    # Resume instructions for agents
├── README.md                    # This file
├── docs/
│   ├── QUALITY-RULES.md         # 42 rules from ArcaneAuditor
│   ├── APP-BUILDER.md           # IDE guide
│   ├── GRAMMAR.md               # Expression language
│   ├── PMD-STRUCTURE.md         # Page properties
│   ├── WIDGETS.md               # 50+ widget types
│   ├── ENDPOINTS.md             # API patterns
│   ├── AMD-STRUCTURE.md         # App metadata
│   ├── SMD-STRUCTURE.md         # Site metadata
│   └── PATTERNS.md              # Reusable patterns
├── examples/
│   ├── buttons.json
│   ├── grids.json
│   ├── flowSurveyPage.json
│   └── ... (20 files)
├── patterns/
│   └── extend-common-issues.json  # 30 common issues to avoid
└── tests/
    └── extend-quality-checklist.json  # Validation checklist
```

## Quality Rules Summary

### ACTION Rules (Must Fix)
| Rule | Requirement |
|------|-------------|
| EndpointFailOnStatusCodes | Add error handling to all endpoints |
| PMDSecurityDomain | Add securityDomains to all pages |
| WidgetIdRequired | Add id to all widgets |
| HardcodedWorkdayAPI | Never hardcode *.workday.com URLs |
| NoIsCollection | Never use isCollection: true |
| ScriptConsoleLog | Remove all console.log statements |

### ADVICE Rules (Should Fix)
| Category | Rules |
|----------|-------|
| Naming | lowerCamelCase everywhere |
| Scripts | let/const, array methods, descriptive names |
| Complexity | Functions <50 lines, nesting <4 levels |
| Security | No hardcoded WIDs or applicationIds |

## Documentation Sources

- "Extend Explained Badly" YouTube series by Jules
- Workday Extend official documentation
- ArcaneAuditor validation rules
- Real-world Extend app patterns

## Contributing

1. Fork this repository
2. Make your changes
3. Submit a pull request

## License

Internal use only - [Your Organization]

## Version History

- **v2.0.0** (2025-12-11) - Added 42 quality rules from ArcaneAuditor
- **v1.0.0** (2025-12-10) - Initial release with PMD documentation
