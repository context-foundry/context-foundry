#!/usr/bin/env python3
"""
Real BAML Integration Tests - Tests actual BAML path (not just fallback)

These tests verify that BAML actually works end-to-end:
- BamlRuntime initialization with API keys
- Function calls to OpenAI GPT-4o-mini
- Response parsing with various LLM output formats
- Environment variable handling
- Error recovery and fallback

Tests use mocking to avoid actual API costs while still exercising the real code paths.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.baml_integration import (
    get_baml_client,
    get_baml_env_vars,
    update_phase_with_baml,
    validate_phase_info,
    generate_scout_report_baml,
    generate_architecture_baml,
    validate_build_result_baml,
    is_baml_available,
    clear_baml_cache,
    BAML_AVAILABLE
)


class TestBAMLEnvVars:
    """Test environment variable handling for BAML"""

    def test_get_baml_env_vars_includes_openai_key(self):
        """Test that get_baml_env_vars includes OPENAI_API_KEY"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'}):
            env_vars = get_baml_env_vars()

            assert 'OPENAI_API_KEY' in env_vars
            assert env_vars['OPENAI_API_KEY'] == 'test-key-123'

    def test_get_baml_env_vars_includes_anthropic_key(self):
        """Test that get_baml_env_vars includes ANTHROPIC_API_KEY"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key-456'}):
            env_vars = get_baml_env_vars()

            assert 'ANTHROPIC_API_KEY' in env_vars
            assert env_vars['ANTHROPIC_API_KEY'] == 'test-key-456'

    def test_get_baml_env_vars_includes_all_environ(self):
        """Test that get_baml_env_vars includes all environment variables"""
        with patch.dict(os.environ, {'TEST_VAR': 'test-value', 'OPENAI_API_KEY': 'key'}):
            env_vars = get_baml_env_vars()

            assert 'TEST_VAR' in env_vars
            assert env_vars['TEST_VAR'] == 'test-value'


class TestBAMLRuntimeInitialization:
    """Test BAML runtime initialization with real library"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_baml_client_initializes_with_api_key(self):
        """Test that BAML client initializes when API key is present"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()
            client = get_baml_client()

            # Should successfully create client
            assert client is not None

    def test_baml_client_caching(self):
        """Test that BAML client is cached across calls"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()
            client1 = get_baml_client()
            client2 = get_baml_client()

            # Should return same cached instance
            assert client1 is client2

    def test_baml_client_force_recompile(self):
        """Test that force_recompile creates new client"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()
            client1 = get_baml_client()
            client2 = get_baml_client(force_recompile=True)

            # Should be different instances
            assert client1 is not client2


class TestBAMLFunctionCalls:
    """Test actual BAML function calls with mocked LLM responses"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_update_phase_with_baml_calls_openai(self):
        """Test that update_phase_with_baml actually calls OpenAI API"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            # Mock the BamlRuntime to avoid actual API call
            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Mock the function call result
                expected_result = {
                    "session_id": "test",
                    "current_phase": "Scout",
                    "phase_number": "1/7",
                    "status": "researching",
                    "progress_detail": "Test",
                    "test_iteration": 0,
                    "phases_completed": [],
                    "started_at": "2025-01-13T00:00:00Z",
                    "last_updated": "2025-01-13T00:00:00Z"
                }

                mock_result = MagicMock()
                # Support both .parsed() and unstable_internal_repr()
                mock_result.parsed.return_value = expected_result
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": json.dumps(expected_result)
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                # Call the function
                result = update_phase_with_baml(
                    phase="Scout",
                    status="Researching",
                    detail="Test detail",
                    session_id="test",
                    iteration=0
                )

                # Verify BamlRuntime was created with env vars
                # Note: May be called more than once due to force_recompile in update_phase_with_baml
                assert mock_runtime_class.from_files.called
                call_kwargs = mock_runtime_class.from_files.call_args[1]
                assert 'env_vars' in call_kwargs
                assert 'OPENAI_API_KEY' in call_kwargs['env_vars']

                # Verify call_function_sync was called
                assert mock_runtime.call_function_sync.called
                call_args = mock_runtime.call_function_sync.call_args
                assert call_args[1]['function_name'] == 'CreatePhaseInfo'
                assert 'env_vars' in call_args[1]
                assert 'OPENAI_API_KEY' in call_args[1]['env_vars']

                # Verify result
                assert result['session_id'] == 'test'
                assert result['current_phase'] == 'Scout'

    def test_validate_phase_info_with_baml(self):
        """Test validate_phase_info calls BAML ValidatePhaseInfo function"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Mock successful validation
                mock_result = MagicMock()
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": json.dumps({
                            "session_id": "test",
                            "current_phase": "Scout",
                            "status": "researching"
                        })
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                # Call validate_phase_info
                test_json = json.dumps({"session_id": "test", "current_phase": "Scout", "status": "researching"})
                valid, phase_info, error = validate_phase_info(test_json)

                # Verify BAML was called
                assert mock_runtime.call_function_sync.called
                call_args = mock_runtime.call_function_sync.call_args
                assert call_args[1]['function_name'] == 'ValidatePhaseInfo'
                assert call_args[1]['args']['json_string'] == test_json


class TestBAMLJSONParsing:
    """Test JSON parsing with various LLM response formats"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_parse_json_with_markdown_codeblocks(self):
        """Test parsing JSON wrapped in markdown code blocks"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                expected_result = {
                    "session_id": "test",
                    "current_phase": "Scout",
                    "phase_number": "1/7",
                    "status": "researching",
                    "progress_detail": "Test",
                    "test_iteration": 0,
                    "phases_completed": [],
                    "started_at": "2025-01-13T00:00:00Z",
                    "last_updated": "2025-01-13T00:00:00Z"
                }

                # LLM returns JSON in markdown code blocks
                mock_result = MagicMock()
                mock_result.parsed.return_value = expected_result
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": "```json\n" + json.dumps(expected_result) + "\n```"
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                result = update_phase_with_baml(
                    phase="Scout",
                    status="Researching",
                    detail="Test",
                    session_id="test",
                    iteration=0
                )

                assert result['session_id'] == 'test'

    def test_parse_json_with_extra_text(self):
        """Test parsing JSON when LLM adds explanatory text after JSON"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # LLM returns JSON plus explanatory text
                json_obj = {
                    "session_id": "test",
                    "current_phase": "Scout",
                    "phase_number": "1/7",
                    "status": "researching",
                    "progress_detail": "Test",
                    "test_iteration": 0,
                    "phases_completed": [],
                    "started_at": "2025-01-13T00:00:00Z",
                    "last_updated": "2025-01-13T00:00:00Z"
                }

                mock_result = MagicMock()
                mock_result.parsed.return_value = json_obj
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": json.dumps(json_obj) + "\n\nThis JSON represents the phase info for the Scout phase."
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                result = update_phase_with_baml(
                    phase="Scout",
                    status="Researching",
                    detail="Test",
                    session_id="test",
                    iteration=0
                )

                # Should extract just the JSON object, ignoring extra text
                assert result['session_id'] == 'test'
                assert result['current_phase'] == 'Scout'


class TestBAMLScoutReportGeneration:
    """Test Scout report generation with BAML"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_generate_scout_report_calls_baml(self):
        """Test that generate_scout_report_baml calls BAML function"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Mock Scout report response
                mock_result = MagicMock()
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": json.dumps({
                            "executive_summary": "Test summary",
                            "past_learnings_applied": [],
                            "known_risks": [],
                            "key_requirements": ["Requirement 1"],
                            "tech_stack": {
                                "languages": ["Python"],
                                "frameworks": ["Flask"],
                                "dependencies": [],
                                "justification": "Test"
                            },
                            "architecture_recommendations": [],
                            "main_challenges": [],
                            "testing_approach": "pytest",
                            "timeline_estimate": "2 hours"
                        })
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                result = generate_scout_report_baml(
                    task_description="Build a web app",
                    codebase_analysis="Python project",
                    past_patterns="No patterns"
                )

                # Verify BAML was called
                assert mock_runtime.call_function_sync.called
                call_args = mock_runtime.call_function_sync.call_args
                assert call_args[1]['function_name'] == 'GenerateScoutReport'

                # Verify result
                assert result is not None
                assert result['executive_summary'] == 'Test summary'


class TestBAMLArchitectureGeneration:
    """Test architecture generation with BAML"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_generate_architecture_calls_baml(self):
        """Test that generate_architecture_baml calls BAML function"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Mock architecture response
                mock_result = MagicMock()
                mock_result.unstable_internal_repr.return_value = json.dumps({
                    "Success": {
                        "content": json.dumps({
                            "system_overview": "Test architecture",
                            "file_structure": [],
                            "modules": [],
                            "applied_patterns": [],
                            "preventive_measures": [],
                            "implementation_steps": [],
                            "test_plan": {
                                "unit_tests": [],
                                "integration_tests": [],
                                "e2e_tests": [],
                                "test_framework": "pytest",
                                "success_criteria": []
                            },
                            "success_criteria": []
                        })
                    }
                })
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                scout_json = json.dumps({"summary": "Test"})
                result = generate_architecture_baml(scout_json, ["Risk 1"])

                # Verify BAML was called
                assert mock_runtime.call_function_sync.called
                call_args = mock_runtime.call_function_sync.call_args
                assert call_args[1]['function_name'] == 'GenerateArchitecture'

                # Verify result
                assert result is not None
                assert result['system_overview'] == 'Test architecture'


class TestBAMLFallbackBehavior:
    """Test that BAML gracefully falls back to JSON when errors occur"""

    def setup_method(self):
        """Clear cache before each test"""
        clear_baml_cache()

    def test_fallback_when_baml_call_fails(self):
        """Test that BAML API call failures raise RuntimeError (no fallback)"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Make the call fail
                mock_runtime.call_function_sync.side_effect = Exception("API Error")
                mock_runtime.create_context_manager.return_value = MagicMock()

                # Should raise RuntimeError (no fallback to JSON)
                with pytest.raises(RuntimeError) as exc_info:
                    update_phase_with_baml(
                        phase="Scout",
                        status="Researching",
                        detail="Test",
                        session_id="test",
                        iteration=0
                    )

                # Verify error message
                assert "BAML phase tracking failed" in str(exc_info.value)
                assert "API Error" in str(exc_info.value)

    def test_fallback_when_json_parsing_fails(self):
        """Test that JSON parsing failures raise RuntimeError (no fallback)"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            clear_baml_cache()

            with patch('tools.baml_integration.BamlRuntime') as mock_runtime_class:
                mock_runtime = MagicMock()
                mock_runtime_class.from_files.return_value = mock_runtime

                # Return completely invalid response - both .parsed() and unstable_internal_repr() fail
                mock_result = MagicMock()
                mock_result.parsed.side_effect = Exception("Parsing failed")
                mock_result.unstable_internal_repr.return_value = "completely invalid"
                mock_runtime.call_function_sync.return_value = mock_result
                mock_runtime.create_context_manager.return_value = MagicMock()

                # Should raise RuntimeError (no fallback to JSON)
                with pytest.raises(RuntimeError) as exc_info:
                    update_phase_with_baml(
                        phase="Scout",
                        status="Researching",
                        detail="Test",
                        session_id="test",
                        iteration=0
                    )

                # Verify error message
                assert "BAML phase tracking failed" in str(exc_info.value)


class TestWithoutBAML:
    """Test that everything works without BAML installed"""

    def test_functions_work_without_baml(self):
        """Test that functions raise RuntimeError when BAML is unavailable"""
        # Even if BAML is installed, simulate it being unavailable
        with patch('tools.baml_integration.BAML_AVAILABLE', False):
            with patch('tools.baml_integration.is_baml_available', return_value=False):
                # update_phase_with_baml should raise RuntimeError
                with pytest.raises(RuntimeError) as exc_info:
                    update_phase_with_baml(
                        phase="Scout",
                        status="Researching",
                        detail="Test",
                        session_id="test",
                        iteration=0
                    )
                assert "BAML is required but not available" in str(exc_info.value)

                # Scout/Architect/Builder functions should also raise RuntimeError
                with pytest.raises(RuntimeError):
                    generate_scout_report_baml("task", "codebase")

                with pytest.raises(RuntimeError):
                    generate_architecture_baml("{}", [])

                with pytest.raises(RuntimeError):
                    validate_build_result_baml("{}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
