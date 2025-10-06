#!/usr/bin/env python3
"""
Test code extraction regex fixes.
Verifies that patterns handle GPT-4o-mini's format (no newline after language).
"""

import re
from pathlib import Path


def test_regex_patterns():
    """Test all code extraction regex patterns with various formats."""

    # These are the fixed patterns from autonomous_orchestrator.py
    patterns = [
        r"File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"file:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"File path:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"##\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"###\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"#+\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
        r"`([^`\n]+\.[a-z]{2,4})`\n```(?:\w+)?[ \t]*\n?(.*?)```",
    ]

    # Test cases from actual weather-app build
    test_cases = [
        # Case 1: GPT-4o-mini format (no newline after javascript)
        {
            "name": "GPT-4o-mini format (no newline)",
            "text": """File: js/components/WeatherCard.js
```javascript
/**
 * Weather Card Component
 */
export class WeatherCard {
  constructor() {
    this.data = null;
  }
}
```""",
            "expected_file": "js/components/WeatherCard.js",
            "expected_code_start": "/**\n * Weather Card Component\n */"
        },
        # Case 2: Standard format (with newline)
        {
            "name": "Standard format (with newline)",
            "text": """File: test.py
```python
def hello():
    print("world")
```""",
            "expected_file": "test.py",
            "expected_code_start": 'def hello():'
        },
        # Case 3: No language specified
        {
            "name": "No language",
            "text": """File: config.json
```
{
  "key": "value"
}
```""",
            "expected_file": "config.json",
            "expected_code_start": '{\n  "key": "value"'
        },
        # Case 4: Lowercase 'file:'
        {
            "name": "Lowercase file:",
            "text": """file: styles.css
```css
body {
  margin: 0;
}
```""",
            "expected_file": "styles.css",
            "expected_code_start": "body {"
        },
        # Case 5: Markdown header format
        {
            "name": "Markdown header",
            "text": """## File: index.html
```html
<!DOCTYPE html>
<html>
</html>
```""",
            "expected_file": "index.html",
            "expected_code_start": "<!DOCTYPE html>"
        },
    ]

    print("=" * 60)
    print("Testing Code Extraction Regex Patterns")
    print("=" * 60)

    all_passed = True

    for test_case in test_cases:
        print(f"\n📝 Test: {test_case['name']}")
        print(f"   Input: {test_case['text'][:50]}...")

        matched = False
        for pattern in patterns:
            matches = list(re.finditer(pattern, test_case['text'], re.DOTALL | re.IGNORECASE))

            if matches:
                match = matches[0]
                filepath = match.group(1).strip()
                code = match.group(2).strip()

                if filepath == test_case['expected_file']:
                    if test_case['expected_code_start'] in code:
                        print(f"   ✅ PASS: Extracted file '{filepath}' with correct code")
                        matched = True
                        break
                    else:
                        print(f"   ❌ FAIL: File correct but code mismatch")
                        print(f"      Expected: {test_case['expected_code_start'][:50]}")
                        print(f"      Got: {code[:50]}")
                        all_passed = False
                        break

        if not matched:
            print(f"   ❌ FAIL: No pattern matched")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("Code extraction regex patterns working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print("Regex patterns need adjustment")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = test_regex_patterns()
    exit(0 if success else 1)
