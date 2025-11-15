"""
Security tests for Code Sandbox - Multi-import bypass vulnerabilities.

These tests verify that the AST-based import validation correctly blocks
ALL modules in comma-separated import statements, preventing bypass attacks.
"""

import pytest

from sandbox import SandboxSecurityError, execute_sandbox_code


def test_multi_import_bypass_blocked():
    """Test that 'import json, numpy' is blocked (numpy not whitelisted)"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import json, numpy\nresult = 1")

    assert "numpy" in str(exc_info.value)
    assert "not in whitelist" in str(exc_info.value)


def test_multi_import_forbidden_blocked():
    """Test that 'import math, os' is blocked (os is forbidden)"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import math, os\nresult = 1")

    assert "os" in str(exc_info.value).lower()


def test_multi_import_all_forbidden_blocked():
    """Test that 'import json, os, sys' is blocked (os and sys forbidden)"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import json, os, sys\nresult = 1")

    # Should block at least one forbidden module
    error_msg = str(exc_info.value).lower()
    assert "os" in error_msg or "sys" in error_msg


def test_aliased_multi_import_blocked():
    """Test that 'import json as j, pandas as pd' is blocked (pandas not whitelisted)"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import json as j, pandas as pd\nresult = 1")

    assert "pandas" in str(exc_info.value)
    assert "not in whitelist" in str(exc_info.value)


def test_from_import_multi_allowed():
    """Test that 'from datetime import datetime, timedelta' passes (both whitelisted)"""
    # datetime is in ALLOWED_IMPORTS, so this should work
    result = execute_sandbox_code(
        code="""
from datetime import datetime, timedelta
result = 'success'
"""
    )
    assert result["success"] is True
    assert result["result"] == "success"


def test_nested_module_blocked():
    """Test that 'import numpy.random' is blocked (numpy not whitelisted)"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import numpy.random\nresult = 1")

    assert "numpy" in str(exc_info.value)


def test_whitelisted_multi_import_allowed():
    """Test that multi-import of whitelisted modules works"""
    result = execute_sandbox_code(
        code="""
import json, math, random
result = json.dumps({'value': math.pi, 'rand': random.random()})
"""
    )
    assert result["success"] is True
    assert result["result"] is not None


def test_mixed_import_blocked():
    """Test that mix of whitelisted and forbidden modules is blocked"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="import json, requests\nresult = 1")

    assert "requests" in str(exc_info.value)
    assert "not in whitelist" in str(exc_info.value)


def test_multiline_imports_blocked():
    """Test that multi-line import statements correctly validate all modules"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(
            code="""
import json
import numpy
result = 1
"""
        )

    assert "numpy" in str(exc_info.value)


def test_from_import_forbidden_blocked():
    """Test that 'from os import listdir' is blocked"""
    with pytest.raises(SandboxSecurityError) as exc_info:
        execute_sandbox_code(code="from os import listdir\nresult = 1")

    assert "os" in str(exc_info.value).lower()
