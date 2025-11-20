# Workday Canvas Kit Extension

Build enterprise-grade, Workday-style React applications with Context Foundry using the official Workday Canvas Kit component library.

## Overview

This extension teaches Context Foundry how to create React applications that look and feel like Workday applications. It provides:

- **Component Library Knowledge**: 30 core Workday Canvas Kit components with usage patterns (~18KB)
- **Design System Principles**: Workday's enterprise design language and best practices
- **Example Applications**: Full working example (COI disclosure app with branching workflow)
- **Branching Workflow Patterns**: Complete state machine patterns for multi-step forms with conditional logic
- **Automatic Detection**: CF automatically detects when to use Canvas Kit based on your prompt

## When to Use This Extension

Context Foundry will automatically use this extension when you:

✅ Mention "Workday Canvas Kit" in your prompt
✅ Request a "Workday-style" application
✅ Build in a directory with `@workday/canvas-kit-react` installed
✅ Ask for specific Canvas Kit components (Modal, FormField, etc.)

## Quick Start

### 1. Create a Workday-Style App

```bash
# Using Context Foundry CLI
cf build

# When prompted, describe your app:
"Create a conflict of interest disclosure app using Workday Canvas Kit.
It should have branching questions based on employee role and a review screen."
```

**What happens:**
- Scout detects "Workday Canvas Kit" keyword
- Loads Canvas Kit component patterns from this extension
- Architect uses COI example as template
- Builder implements using Canvas Kit components
- Result: Professional Workday-style React app

### 2. Use CF Daemon for Background Builds

```bash
# Start daemon
cfd start

# Submit Canvas Kit project
cfd submit --type autonomous_build --params '{
  "task": "Create employee onboarding form with Workday Canvas Kit",
  "working_directory": "/path/to/project"
}'

# Monitor progress
cfd logs <job-id> --follow
```

## Extension Structure

```
/extensions/workday-canvas/
├── patterns/
│   └── canvas-kit-expertise.json    # Complete component library reference
├── examples/
│   └── conflict-of-interest/        # Full COI app example
│       └── README.md               # Detailed implementation guide
├── components/
│   ├── forms/                       # Form component patterns
│   ├── tables/                      # Table component patterns
│   └── workflows/                   # Branching workflow patterns
│       └── README.md               # Complete workflow implementation guide
├── tests/
│   └── test_canvas_detection.py    # Extension tests
├── detector.py                      # Project detection logic
├── extensions_loader.py             # Pattern loading
└── README.md                        # This file
```

## Component Library

### Categories

The extension includes patterns for **30 core Canvas Kit components** across 8 categories:

**Buttons** (5): PrimaryButton, SecondaryButton, TertiaryButton, DeleteButton, SegmentedControl
**Forms** (7): FormField, TextInput, TextArea, Select, Checkbox, Radio, Switch
**Layout** (4): Box, Flex, Grid, Stack
**Popups** (3): Modal, Popup, Tooltip
**Navigation** (2): Menu, Tabs
**Containers** (2): Card, Table
**Feedback** (4): Toast, Banner, LoadingDots, StatusIndicator
**Icons** (3): SystemIcon, AccentIcon, AppletIcon

See `patterns/canvas-kit-expertise.json` (~18KB) for complete component reference.

**Note**: Additional component subdirectories (`components/forms/`, `components/tables/`) are placeholders for future pattern expansions. Currently only `components/workflows/` has documentation.

## Example Applications

### Conflict of Interest Disclosure App

Location: `examples/conflict-of-interest/`

**Features:**
- Branching questionnaire (role-based questions)
- Conditional validation
- Progress tracking
- Review/edit screen
- Approval workflow routing

**Use as template:**
```
"Create a COI disclosure app like the example in /extensions/workday-canvas/examples/conflict-of-interest/"
```

CF will read the example README and implement a similar structure for your use case.

## Common Patterns

### 1. Branching Workflows

Perfect for: Multi-step forms, conditional questionnaires, approval workflows

```typescript
// Question with conditional next step
const questions = [
  {
    id: 'q1-role',
    text: 'What is your role?',
    type: 'radio',
    options: ['Employee', 'Manager', 'Executive'],
    next: (answer) => {
      if (answer === 'Manager') return 'q2-manager';
      if (answer === 'Executive') return 'q2-exec';
      return 'q2-employee';
    }
  }
];
```

**Full pattern guide**: `components/workflows/README.md`

### 2. Form Validation

```tsx
import { FormField } from '@workday/canvas-kit-react/form-field';
import { TextInput } from '@workday/canvas-kit-react/text-input';

<FormField error={error ? FormField.ErrorType.Error : undefined}>
  <FormField.Label>Email</FormField.Label>
  <FormField.Input
    type="email"
    value={email}
    onChange={handleChange}
  />
  {error && <FormField.Hint>{error}</FormField.Hint>}
</FormField>
```

### 3. Data Tables

```tsx
import { Table } from '@workday/canvas-kit-react/table';

<Table>
  <Table.Head>
    <Table.Row>
      <Table.Header>Name</Table.Header>
      <Table.Header>Status</Table.Header>
    </Table.Row>
  </Table.Head>
  <Table.Body>
    {data.map(row => (
      <Table.Row key={row.id}>
        <Table.Cell>{row.name}</Table.Cell>
        <Table.Cell>{row.status}</Table.Cell>
      </Table.Row>
    ))}
  </Table.Body>
</Table>
```

## Project Detection

The extension automatically detects Canvas Kit projects by:

1. **Prompt Keywords**: "Workday", "Canvas Kit", "Workday-style"
2. **Package.json**: Checks for `@workday/canvas-kit-react` dependency
3. **Import Statements**: Scans src/ for Canvas Kit imports

**Detection output:**
```
🔍 Workday Canvas Kit Extension: Detected Canvas Kit project
   - Version: 13.2.19
   - TypeScript: True
   - Uses Emotion: True
   - Component Imports: ~24
✅ Setting canvas_kit_project=True in CONFIGURATION
```

## How Context Foundry Uses This Extension

### Scout Phase
- Detects Canvas Kit keywords in prompt
- Loads `canvas-kit-expertise.json` patterns
- Identifies project type as "workday-canvas"
- Adds Canvas Kit installation requirements

### Architect Phase
- References component categories for UI structure
- Uses branching workflow patterns for conditional flows
- Checks example apps for similar use cases
- Plans CanvasProvider wrapper and theme setup

### Builder Phase
- Implements using Canvas Kit components (not generic React)
- Follows compound component patterns (Modal.Card, Modal.Heading)
- Uses FormField wrappers for all inputs
- Applies proper TypeScript types from Canvas Kit packages

### Test Phase
- Tests accessibility with jest-axe
- Tests keyboard navigation
- Tests form validation
- Mocks Canvas Kit components as needed

## Installation Requirements

When CF detects a Canvas Kit project, it ensures these are installed:

```json
{
  "dependencies": {
    "@workday/canvas-kit-react": "^13.0.0",
    "@workday/canvas-tokens-web": "^2.0.0",
    "@emotion/react": "^11.7.0",
    "@emotion/styled": "^11.7.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0"
  }
}
```

## Usage Examples

### Example 1: Simple Form

**Prompt:**
```
"Create a user profile form using Workday Canvas Kit with name, email, and department fields"
```

**Result:**
- FormField components for each input
- Proper validation and error states
- PrimaryButton for submit
- CanvasProvider wrapper
- TypeScript types

### Example 2: Branching Workflow

**Prompt:**
```
"Create an expense approval workflow with Canvas Kit. Route to different approvers based on amount:
- < $1000: Manager approval
- $1000-$10000: Director approval
- > $10000: VP approval"
```

**Result:**
- Multi-step form with amount input
- Conditional routing based on value
- Progress indicator (Stepper)
- Review screen with approval status
- Uses workflow patterns from this extension

### Example 3: Data Table App

**Prompt:**
```
"Create an employee directory with Canvas Kit Table, sorting, and search"
```

**Result:**
- Table component with sortable columns
- TextInput for search
- Select for department filter
- PrimaryButton for "Add Employee"
- Card wrapper for table

## Best Practices

The extension teaches CF to follow Workday's design principles:

1. ✅ **Use Canvas Kit components** - Not custom React components
2. ✅ **Wrap app in CanvasProvider** - Required at root
3. ✅ **Import CSS variables** - `@workday/canvas-tokens-web/css/base/_variables.css`
4. ✅ **Use compound components correctly** - Modal.Card, not custom Modal wrapper
5. ✅ **Follow TypeScript types** - Import from Canvas Kit packages
6. ✅ **Accessibility first** - Canvas Kit is WCAG 2.1 AA compliant

7. ❌ **Don't mix design systems** - No Material-UI with Canvas Kit
8. ❌ **Don't override styles directly** - Use theme tokens
9. ❌ **Don't skip CanvasProvider** - Required for theme management

## Testing the Extension

```bash
# Test Canvas Kit detection (runs all 4 test suites)
python3 scripts/test_canvas_kit_extension.py

# Expected output:
# ✅ Extension structure test PASSED
# ✅ Pattern file test PASSED (30 components)
# ✅ Detector import test PASSED
# ✅ Prompt detection test PASSED
# 🎉 All tests PASSED!

# Test with CF daemon
cfd submit --type autonomous_build --params '{
  "task": "Create a simple Canvas Kit app with a form",
  "working_directory": "/tmp/test-canvas-kit"
}'
```

**Note**: The `tests/` directory within the extension is currently empty (placeholder for future pytest-based tests). The main test suite is `scripts/test_canvas_kit_extension.py`.

## Customization

### Add New Component Patterns

Edit `patterns/canvas-kit-expertise.json`:

```json
{
  "component_library": {
    "categories": {
      "your-category": {
        "description": "Your category description",
        "components": [
          {
            "name": "YourComponent",
            "import": "@workday/canvas-kit-react/your-component",
            "use_case": "When to use this",
            "example": "<YourComponent />"
          }
        ]
      }
    }
  }
}
```

### Add New Examples

1. Create directory: `examples/your-example/`
2. Add `README.md` with implementation guide
3. Include code samples and use cases
4. CF will reference it when users request similar apps

## Troubleshooting

### Extension Not Loading

**Symptom**: CF doesn't detect Canvas Kit in your prompt

**Solution**:
1. Check extension exists: `ls /path/to/context-foundry/extensions/workday-canvas/`
2. Verify `canvas-kit-expertise.json` exists in `patterns/`
3. Use explicit keywords: "Workday Canvas Kit" in your prompt

### Components Not Recognized

**Symptom**: CF uses generic React components instead of Canvas Kit

**Solution**:
1. Ensure prompt mentions "Canvas Kit" or "Workday"
2. Check `package.json` has `@workday/canvas-kit-react`
3. Verify extension patterns loaded (check Scout phase logs)

### Import Errors

**Symptom**: Generated code has incorrect imports

**Solution**:
1. Verify Canvas Kit version in patterns matches your project
2. Check component names match exactly (case-sensitive)
3. Review `patterns/canvas-kit-expertise.json` component imports

## Resources

- **Canvas Kit Documentation**: https://canvas.workday.com/
- **Component Storybook**: https://workday.github.io/canvas-kit/
- **GitHub Repository**: https://github.com/Workday/canvas-kit
- **NPM Package**: https://www.npmjs.com/package/@workday/canvas-kit-react

## Contributing

To improve this extension:

1. Add new component patterns to `patterns/canvas-kit-expertise.json`
2. Create example apps in `examples/`
3. Document patterns in `components/`
4. Test with CF daemon
5. Share learnings with community

## Version & Stats

**Extension Version**: 1.0.0
**Canvas Kit Version**: v13.x (compatible with v11-v14)
**Last Updated**: 2025-11-19
**Components Documented**: 30 core components
**Pattern File Size**: ~18KB
**Example Apps**: 1 (Conflict of Interest)
**Workflow Patterns**: Complete branching logic implementation guide

### Current Status

✅ **Core extension complete** - Detector, loader, patterns, examples
✅ **30 components documented** - All major Canvas Kit categories covered
✅ **Branching workflows** - Complete implementation guide with code samples
✅ **COI example app** - Full template with TypeScript, validation, state management
🔄 **Forms patterns** - Placeholder (future expansion)
🔄 **Tables patterns** - Placeholder (future expansion)
🔄 **Pytest tests** - Placeholder (currently using `scripts/test_canvas_kit_extension.py`)

---

**Built with Context Foundry** - Autonomous software development system
**Powered by Workday Canvas Kit** - Enterprise design system
