# Teaching Claude New Programming Languages

**Version:** 1.0.0
**Last Updated:** 2025-12-09

This guide explains how to teach Context Foundry (and Claude) a programming language that is **not in Claude's training data**. This applies to:

- New/experimental languages
- Domain-specific languages (DSLs)
- Proprietary scripting languages
- Languages created after Claude's knowledge cutoff

---

## Table of Contents

1. [Overview](#overview)
2. [What You Need to Provide](#what-you-need-to-provide)
3. [Understanding BNF Grammar](#understanding-bnf-grammar)
4. [Understanding Type System Rules](#understanding-type-system-rules)
5. [Extension Structure](#extension-structure)
6. [How Context Flows to Subagents](#how-context-flows-to-subagents)
7. [Pattern JSON Structure](#pattern-json-structure)
8. [Step-by-Step Guide](#step-by-step-guide)
9. [Examples](#examples)
10. [Testing Your Extension](#testing-your-extension)

---

## Overview

Claude learns new languages through **structured context injection**. The system works like this:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Your Language Materials                          │
├─────────────────────────────────────────────────────────────────────┤
│  Grammar (BNF)  │  Type Rules  │  Stdlib  │  Examples  │  Patterns  │
└────────┬────────┴──────┬───────┴────┬─────┴─────┬──────┴─────┬──────┘
         │               │            │           │            │
         ▼               ▼            ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  extensions/{language}/                              │
│  CLAUDE.md → docs/ → patterns/ → templates/ → prompts/              │
└────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Orchestrator reads CLAUDE.md                           │
│      "If working on {language}, read extensions/{language}/"         │
└────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Subagents get explicit instructions                     │
│  "Read extensions/{lang}/CLAUDE.md first. Use patterns from..."      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## What You Need to Provide

To teach Claude a new language, provide these materials:

| Material | Required? | Purpose | Format |
|----------|-----------|---------|--------|
| **Grammar/Syntax** | Yes | How to write valid code | BNF/EBNF or prose |
| **Type System** | Yes (if typed) | Type rules and constraints | Rules + examples |
| **Standard Library** | Yes | Built-in functions/types | Reference docs |
| **Code Examples** | Yes | Working code samples | Source files |
| **Common Mistakes** | Recommended | Anti-patterns to avoid | Pattern JSON |
| **Idioms** | Recommended | "The right way" to do things | Examples + explanation |

### Minimum Viable Language Extension

At minimum, you need:

1. **5-10 working code examples** (varied complexity)
2. **Syntax rules** (what's valid, what's not)
3. **Error patterns** (common mistakes beginners make)

---

## Understanding BNF Grammar

### What is BNF?

**BNF** stands for **Backus-Naur Form** (or Backus Normal Form). It's a notation for describing the syntax (grammar) of programming languages.

Think of it as "rules for building valid sentences" in a programming language.

### BNF Syntax Basics

```
<symbol> ::= expression
```

- `<symbol>` - A non-terminal (something that can be expanded)
- `::=` - "is defined as"
- `expression` - What the symbol expands to

### Special Characters

| Symbol | Meaning | Example |
|--------|---------|---------|
| `::=` | "is defined as" | `<digit> ::= 0 \| 1 \| 2` |
| `\|` | "or" (alternatives) | `<bool> ::= true \| false` |
| `< >` | Non-terminal (rule name) | `<expression>` |
| `" "` | Terminal (literal text) | `"if"` |
| `[ ]` | Optional (0 or 1) | `["else" <statement>]` |
| `{ }` | Repetition (0 or more) | `{<statement>}` |

### Example: Simple Expression Language

```bnf
<program>     ::= {<statement>}

<statement>   ::= <assignment> | <if_stmt> | <print_stmt>

<assignment>  ::= <identifier> "=" <expression> ";"

<if_stmt>     ::= "if" "(" <expression> ")" "{" {<statement>} "}"
                  ["else" "{" {<statement>} "}"]

<print_stmt>  ::= "print" "(" <expression> ")" ";"

<expression>  ::= <term> {("+" | "-") <term>}

<term>        ::= <factor> {("*" | "/") <factor>}

<factor>      ::= <number> | <identifier> | "(" <expression> ")"

<identifier>  ::= <letter> {<letter> | <digit>}

<number>      ::= <digit> {<digit>}

<letter>      ::= "a" | "b" | ... | "z" | "A" | "B" | ... | "Z"

<digit>       ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
```

This grammar defines a language where you can write:

```
x = 5;
y = x + 10;
if (y > 10) {
    print(y);
} else {
    print(0);
}
```

### Example: Function Definition Grammar

```bnf
<function_def>  ::= "func" <identifier> "(" [<param_list>] ")" ["->" <type>] "{"
                    {<statement>}
                    "}"

<param_list>    ::= <param> {"," <param>}

<param>         ::= <identifier> ":" <type>

<type>          ::= "int" | "string" | "bool" | "void" | <identifier>
```

This allows:

```
func add(a: int, b: int) -> int {
    return a + b;
}

func greet(name: string) {
    print("Hello, " + name);
}
```

### What to Include in Your Grammar

For Claude to understand your language, document:

1. **Literals** - Numbers, strings, booleans
2. **Identifiers** - Variable/function naming rules
3. **Operators** - Arithmetic, comparison, logical
4. **Statements** - Assignment, conditionals, loops
5. **Expressions** - How values are computed
6. **Declarations** - Variables, functions, types
7. **Comments** - Single-line, multi-line

### Alternative: Prose Description

If BNF feels too formal, you can describe syntax in prose:

```markdown
## Variable Declaration

Variables are declared with `let` followed by the name, a colon, the type,
and optionally an initial value:

    let x: int = 5;
    let name: string;  // uninitialized

Names must start with a letter or underscore, followed by letters, digits,
or underscores. Names are case-sensitive.

## If Statements

If statements use parentheses around the condition and curly braces for the body:

    if (x > 0) {
        print("positive");
    } else if (x < 0) {
        print("negative");
    } else {
        print("zero");
    }

The `else` and `else if` branches are optional.
```

---

## Understanding Type System Rules

### What are Type System Rules?

Type system rules define:

1. **What types exist** in the language
2. **How types interact** (can you add a string to a number?)
3. **When type errors occur**
4. **How types are inferred** (if at all)

### Categories of Type Systems

| Category | Description | Example Languages |
|----------|-------------|-------------------|
| **Static** | Types checked at compile time | Java, TypeScript, Rust |
| **Dynamic** | Types checked at runtime | Python, JavaScript, Ruby |
| **Strong** | No implicit type coercion | Python, Rust |
| **Weak** | Implicit type coercion allowed | JavaScript, C |
| **Inferred** | Types deduced by compiler | Rust, Haskell, TypeScript |
| **Manifest** | Types must be declared | Java, C |

### Example: Type Rules for a Simple Language

```markdown
## Primitive Types

| Type | Description | Literals |
|------|-------------|----------|
| `int` | 64-bit signed integer | `42`, `-17`, `0` |
| `float` | 64-bit floating point | `3.14`, `-0.5`, `1e10` |
| `string` | UTF-8 text | `"hello"`, `'world'` |
| `bool` | Boolean | `true`, `false` |
| `void` | No value | (no literal) |

## Type Compatibility Rules

### Arithmetic Operations (+, -, *, /)

| Left | Right | Result | Notes |
|------|-------|--------|-------|
| int | int | int | |
| float | float | float | |
| int | float | float | int promoted to float |
| string | string | string | concatenation (+ only) |
| string | int | **ERROR** | use `str(int)` to convert |

### Comparison Operations (==, !=, <, >, <=, >=)

| Left | Right | Result | Notes |
|------|-------|--------|-------|
| int | int | bool | |
| float | float | bool | |
| string | string | bool | lexicographic comparison |
| int | float | bool | int promoted to float |
| bool | bool | bool | == and != only |

### Logical Operations (&&, ||, !)

| Operand(s) | Result | Notes |
|------------|--------|-------|
| bool | bool | |
| int | **ERROR** | no implicit truthiness |

## Type Inference Rules

Variables infer their type from initialization:

```
let x = 5;        // x is int
let y = 3.14;     // y is float
let z = "hello";  // z is string
let flag = true;  // flag is bool
```

Uninitialized variables MUST have explicit types:

```
let x: int;       // OK
let y;            // ERROR: cannot infer type
```

## Type Errors

Common type errors and their messages:

| Error | Example | Message |
|-------|---------|---------|
| Type mismatch | `"a" + 5` | `Cannot apply '+' to string and int` |
| Undefined variable | `print(x)` | `Undefined variable 'x'` |
| Wrong argument type | `sqrt("4")` | `Expected float, got string` |
| Wrong return type | `func f() -> int { return "x"; }` | `Cannot return string from int function` |
```

### Example: Subtyping Rules

If your language has inheritance or interfaces:

```markdown
## Subtyping

A type `A` is a subtype of `B` (written `A <: B`) if a value of type `A`
can be used wherever a value of type `B` is expected.

### Class Inheritance

If `class Dog extends Animal`, then `Dog <: Animal`.

```
let pet: Animal = Dog("Rex");  // OK: Dog <: Animal
let dog: Dog = Animal();       // ERROR: Animal is not Dog
```

### Interface Implementation

If `class File implements Readable`, then `File <: Readable`.

```
func read(r: Readable) { ... }
read(File("test.txt"));  // OK: File <: Readable
```

### Covariance and Contravariance

- Return types are **covariant**: if `Dog <: Animal`, then `() -> Dog <: () -> Animal`
- Argument types are **contravariant**: if `Dog <: Animal`, then `(Animal) -> void <: (Dog) -> void`
```

---

## Extension Structure

Create this folder structure for your new language:

```
extensions/{language-name}/
├── CLAUDE.md                          # Entry point (REQUIRED)
├── __init__.py                        # Python package marker
├── detector.py                        # Project detection
├── extensions_loader.py               # Safe loading interface
│
├── docs/
│   ├── GRAMMAR.md                     # BNF/EBNF or prose syntax
│   ├── TYPE-SYSTEM.md                 # Type rules
│   ├── STDLIB.md                      # Standard library reference
│   ├── IDIOMS.md                      # Idiomatic patterns
│   └── ARTIFACT_CONTRACT.md           # What builds produce
│
├── patterns/
│   └── {lang}-common-issues.json      # Known pitfalls
│
├── templates/
│   ├── hello-world.{ext}              # Basic example
│   ├── data-structures.{ext}          # Collections, maps, etc.
│   ├── functions.{ext}                # Function examples
│   ├── error-handling.{ext}           # Try/catch, Result types
│   └── async.{ext}                    # Concurrency (if applicable)
│
├── prompts/
│   ├── SCOUT-PROJECT-ASSESSMENT.md    # Research guidance
│   ├── BUILDER-BEST-PRACTICES.md      # Code style guide
│   └── TESTER-VALIDATION.md           # Testing guidance
│
└── tests/
    └── test_detector.py               # Detection tests
```

### CLAUDE.md Template

This is the **entry point** that tells Claude how to use the extension:

```markdown
# Context Foundry - {Language Name} Extension

## Before Starting ANY {Language} Work

**IMPORTANT:** Read learned patterns first to avoid known issues:

Read the local patterns file directly:
- `patterns/{lang}-common-issues.json`

Or use MCP:
```lua
mcp__context-foundry__read_global_patterns("common-issues")
-- Look for patterns with domain: "{language}"
```

## Critical Patterns to Know

### 1. {Most Common Mistake}
**{What to do instead}**

{Brief explanation}

```{ext}
// BAD: {anti-pattern}
{bad_code}

// GOOD: {correct pattern}
{good_code}
```

### 2. {Second Common Mistake}
...

## Directory Structure

```
scripts/
├── build.{ext}              ← Main build script
├── run.{ext}                ← Entry point
└── lib/                     ← Shared libraries

patterns/
└── {lang}-common-issues.json  ← LEARNED ISSUES & SOLUTIONS
```

## Common Commands

```bash
# Build the project
{build_command}

# Run the project
{run_command}

# Run tests
{test_command}
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `docs/GRAMMAR.md` | Language syntax reference |
| `docs/TYPE-SYSTEM.md` | Type rules |
| `docs/STDLIB.md` | Standard library |
| `patterns/{lang}-common-issues.json` | Learned issues & solutions |

## After Solving Issues

When you solve a new problem, save the pattern:

1. Add to `patterns/{lang}-common-issues.json`
2. Merge to global: `mcp__context-foundry__merge_project_patterns(path, "common-issues")`
```

---

## How Context Flows to Subagents

### The Key Question

> "Do we tell subagents where the .md files are stored, or will the MCP server do that?"

**Answer: The orchestrator explicitly tells subagents what to read.**

### The Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  User: "Build me an app in NewLang"                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. ORCHESTRATOR reads root CLAUDE.md                                │
│     Sees: "If NewLang work → read extensions/newlang/CLAUDE.md"      │
│     Optionally calls: mcp__context-foundry__read_global_patterns()   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. ORCHESTRATOR spawns SCOUT with explicit instructions:            │
│                                                                      │
│     "You are researching a NewLang project.                          │
│      IMPORTANT: Read these files first:                              │
│      - extensions/newlang/CLAUDE.md                                  │
│      - extensions/newlang/docs/GRAMMAR.md                            │
│      - extensions/newlang/patterns/newlang-common-issues.json        │
│                                                                      │
│      This language has these key characteristics: [summary]          │
│      Known issues to watch for: [from patterns]"                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. SCOUT reads the extension files, learns the language             │
│     Returns analysis with language-specific findings                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. ORCHESTRATOR spawns BUILDER with:                                │
│     - Same extension context                                         │
│     - Scout's findings                                               │
│     - Architecture plan                                              │
│     - "Reference templates in extensions/newlang/templates/"         │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Insight

**Subagents don't auto-discover context.** The orchestrator must:

1. Read root `CLAUDE.md` to learn about extensions
2. Detect the project type (via MCP server or file inspection)
3. Explicitly include extension paths in task prompts

### Implementation in Root CLAUDE.md

Update the root `CLAUDE.md` to include your extension:

```markdown
## Extensions

Context Foundry has domain-specific extensions. **When working on tasks for
a specific domain, read that extension's CLAUDE.md first.**

### {Your Language} Extension
**Location:** `extensions/{language}/`
**When to read:** Any {language} work

**IMPORTANT - Read before {language} work:**
- `extensions/{language}/CLAUDE.md` - Critical patterns and commands
- `extensions/{language}/patterns/{lang}-common-issues.json` - Learned issues

**Key learnings:**
- {Bullet point 1}
- {Bullet point 2}
```

---

## Pattern JSON Structure

### Common Issues Pattern File

**File:** `patterns/{lang}-common-issues.json`

```json
{
  "pattern_type": "common-issues",
  "domain": "{language}",
  "version": "1.0.0",
  "last_updated": "2025-12-09",

  "patterns": [
    {
      "id": "{lang}-issue-identifier",
      "title": "Human-readable title describing the issue",
      "symptoms": [
        "What the user sees when this goes wrong",
        "Error messages that appear",
        "Unexpected behavior description"
      ],
      "root_cause": "Technical explanation of WHY this happens",
      "solution": "How to fix it - clear, actionable steps",
      "bad_code": "// Code that causes the problem\nbroken_example()",
      "good_code": "// Code that works correctly\nworking_example()",
      "frequency": 1,
      "severity": "high",
      "learned_from": "Description of when this was discovered"
    }
  ],

  "recommended_workflow": {
    "description": "Best practice workflow for this language",
    "steps": [
      "1. First step",
      "2. Second step",
      "3. Third step"
    ]
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, use `{lang}-descriptive-name` |
| `title` | string | Short description of the issue |
| `symptoms` | array | What users observe when this happens |
| `root_cause` | string | Technical explanation of why |
| `solution` | string | How to fix it |
| `bad_code` | string | Example of problematic code |
| `good_code` | string | Example of correct code |
| `frequency` | number | How often this occurs (incremented on each occurrence) |
| `severity` | string | "low", "medium", "high", or "critical" |
| `learned_from` | string | Context of when/how this was discovered |

### Example: Real Pattern from Roblox Extension

```json
{
  "id": "roblox-cframe-vs-position",
  "title": "Position property doesn't persist in Lune",
  "symptoms": [
    "All cloned objects appear at same location",
    "setPosition appears to do nothing",
    "Objects stacked on top of each other"
  ],
  "root_cause": "Lune's roblox module doesn't reliably save Position property changes. Must use CFrame instead.",
  "solution": "Use `part.CFrame = oldCFrame + Vector3.new(offsetX, offsetY, offsetZ)` to move parts while preserving rotation.",
  "bad_code": "part.Position = Vector3.new(x, y, z)",
  "good_code": "part.CFrame = oldCFrame + Vector3.new(offsetX, offsetY, offsetZ)",
  "frequency": 3,
  "severity": "high",
  "learned_from": "cabin positioning debugging session"
}
```

---

## Step-by-Step Guide

### Step 1: Gather Materials

Collect these from the language documentation or creators:

- [ ] Language specification or grammar
- [ ] Type system documentation
- [ ] Standard library reference
- [ ] 5-10 working code examples
- [ ] Known gotchas or common mistakes

### Step 2: Create Extension Directory

```bash
mkdir -p extensions/{language}/{docs,patterns,templates,prompts,tests}
touch extensions/{language}/__init__.py
```

### Step 3: Write GRAMMAR.md

Document the syntax using BNF or prose (see [Understanding BNF Grammar](#understanding-bnf-grammar)).

### Step 4: Write TYPE-SYSTEM.md

Document type rules and constraints (see [Understanding Type System Rules](#understanding-type-system-rules)).

### Step 5: Create Code Templates

Add working examples to `templates/`:

```bash
# Create basic examples
cat > extensions/{language}/templates/hello-world.{ext} << 'EOF'
// Hello World in {Language}
{hello_world_code}
EOF
```

### Step 6: Document Common Issues

Create `patterns/{lang}-common-issues.json` with known pitfalls.

### Step 7: Write CLAUDE.md

Create the entry point that references all other files.

### Step 8: Update Root CLAUDE.md

Add your extension to the extensions table in the root `CLAUDE.md`.

### Step 9: Implement Detector (Optional but Recommended)

Create `detector.py` to auto-detect projects:

```python
from pathlib import Path
from typing import Dict, Any

def detect_{lang}_project(directory: Path) -> Dict[str, Any]:
    """Detect {Language} project."""
    # Check for language-specific files
    has_config = (directory / "{lang}.config").exists()
    has_source = any(directory.glob("**/*.{ext}"))

    if not (has_config or has_source):
        return {"is_{lang}_project": False}

    return {
        "is_{lang}_project": True,
        "project_type": "{lang}-app",
        "confidence": "high"
    }
```

### Step 10: Test with a Build

```bash
# Create a test project
mkdir test-{lang}-project
cd test-{lang}-project

# Run Context Foundry
cf build "Create a simple {language} application that..."
```

---

## Examples

### Example 1: Minimal DSL Extension

For a simple domain-specific language:

```
extensions/mydsl/
├── CLAUDE.md
├── docs/
│   └── GRAMMAR.md              # 50-line BNF
├── patterns/
│   └── mydsl-common-issues.json   # 3-5 patterns
└── templates/
    └── example.mydsl           # 1 working example
```

### Example 2: Full Programming Language

For a complete language like Luau (Roblox's Lua variant):

```
extensions/luau/
├── CLAUDE.md
├── __init__.py
├── detector.py
├── extensions_loader.py
├── docs/
│   ├── GRAMMAR.md              # Full BNF (~500 lines)
│   ├── TYPE-SYSTEM.md          # Type rules (~200 lines)
│   ├── STDLIB.md               # Standard library (~1000 lines)
│   ├── IDIOMS.md               # Best practices (~300 lines)
│   └── ARTIFACT_CONTRACT.md
├── patterns/
│   ├── luau-common-issues.json
│   └── luau-security-patterns.json
├── templates/
│   ├── hello-world.luau
│   ├── data-structures.luau
│   ├── functions.luau
│   ├── classes.luau
│   ├── async-patterns.luau
│   └── error-handling.luau
├── prompts/
│   ├── SCOUT-PROJECT-ASSESSMENT.md
│   ├── ARCHITECT-SYSTEMS.md
│   ├── BUILDER-BEST-PRACTICES.md
│   └── TESTER-STRATEGY.md
└── tests/
    ├── test_detector.py
    └── test_patterns.py
```

---

## Testing Your Extension

### Manual Verification

1. **Read test**: Can Claude read and understand your grammar?
   ```
   "Read extensions/{lang}/docs/GRAMMAR.md and explain how to write a function"
   ```

2. **Write test**: Can Claude write valid code?
   ```
   "Write a {language} function that calculates fibonacci numbers"
   ```

3. **Debug test**: Can Claude fix broken code?
   ```
   "This {language} code has a bug: [broken code]. Fix it."
   ```

### Automated Tests

Create `tests/test_integration.py`:

```python
import pytest
from pathlib import Path

def test_grammar_file_exists():
    """Verify grammar documentation exists."""
    grammar = Path("extensions/{lang}/docs/GRAMMAR.md")
    assert grammar.exists()
    assert grammar.read_text().strip() != ""

def test_patterns_valid_json():
    """Verify patterns file is valid JSON."""
    import json
    patterns = Path("extensions/{lang}/patterns/{lang}-common-issues.json")
    data = json.loads(patterns.read_text())
    assert "patterns" in data
    assert len(data["patterns"]) > 0

def test_templates_exist():
    """Verify code templates exist."""
    templates = Path("extensions/{lang}/templates")
    files = list(templates.glob("*.{ext}"))
    assert len(files) >= 1, "Need at least one code template"
```

---

## Summary

To teach Claude a new programming language:

1. **Provide grammar** (BNF or prose description of syntax)
2. **Document type rules** (if the language is typed)
3. **Include working examples** (5-10 varied code samples)
4. **Document common mistakes** (patterns JSON with bad/good code)
5. **Create CLAUDE.md** entry point that references all materials
6. **Update root CLAUDE.md** to include your extension

The orchestrator will read CLAUDE.md and explicitly tell subagents where to find your language documentation. Subagents don't auto-discover - they need explicit instructions.

---

## Related Documentation

- [Extension Development Guide](EXTENSION_DEVELOPMENT_GUIDE.md) - Full extension development reference
- [Pattern Sharing](PATTERN_SHARING.md) - How patterns propagate globally
- [Multi-Agent Architecture](MULTI_AGENT_ARCHITECTURE.md) - How phases/agents work

---

**Version History:**
- 1.0.0 (2025-12-09) - Initial guide
