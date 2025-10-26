"""Tests for document processing functionality."""

import pytest
from pathlib import Path
from examples.document_processing import analyze_document


@pytest.mark.asyncio
async def test_analyze_document_structure(sample_document, sample_questions):
    """Test that analyze_document returns correct structure."""
    # Create test file if doesn't exist
    if not sample_document.exists():
        sample_document.parent.mkdir(parents=True, exist_ok=True)
        sample_document.write_text("Test document content")

    result = await analyze_document(str(sample_document), sample_questions)

    # Verify structure
    assert "summary" in result
    assert "key_findings" in result
    assert "answers" in result
    assert "confidence_score" in result

    # Verify types
    assert isinstance(result["summary"], str)
    assert isinstance(result["key_findings"], list)
    assert isinstance(result["answers"], dict)
    assert isinstance(result["confidence_score"], float)

    # Verify confidence score range
    assert 0.0 <= result["confidence_score"] <= 1.0


@pytest.mark.asyncio
async def test_analyze_document_missing_file(sample_questions):
    """Test handling of missing document."""
    with pytest.raises(FileNotFoundError):
        await analyze_document("/nonexistent/file.pdf", sample_questions)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_document_integration(test_config, sample_document, sample_questions):
    """Integration test with real API (requires API key)."""
    if not test_config["run_integration_tests"]:
        pytest.skip("Integration tests disabled")

    result = await analyze_document(str(sample_document), sample_questions)

    # Verify real API response
    assert len(result["summary"]) > 0
    assert len(result["key_findings"]) > 0
    assert len(result["answers"]) == len(sample_questions)
