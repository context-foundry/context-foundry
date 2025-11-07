"""
MCP Delegation Example - FREE, Unlimited Agent Skills

This example demonstrates using Context Foundry's Meta-MCP pattern to execute
BAML-style functions WITHOUT any API costs.

KEY INNOVATION:
Instead of making paid API calls, we spawn Claude instances via MCP delegation.
These spawned instances:
- Run on your Claude Code subscription (FREE, unlimited)
- Have full access to Agent Skills
- Get fresh 200K token context windows
- Inherit Claude Code authentication (no API keys needed)

COST COMPARISON:
- Direct API calls: $3-15 per 1M tokens
- MCP delegation: $0 (subscription-based, unlimited)

This is the TRUE Context Foundry way - Meta-MCP all the way down!
"""

import asyncio
import logging
import sys
from pathlib import Path

# Import MCP executor (replaces BAML API client)
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_executor import executor
from shared.config import load_config
from shared.utils import setup_logging

logger = logging.getLogger("baml_mcp.examples")


async def document_processing_example():
    """
    Example: Process a PDF document using MCP-spawned Claude with Agent Skills.

    This demonstrates:
    - Zero cost (runs on subscription)
    - Agent Skills available in spawned instance
    - Structured output matching BAML schema
    - No API keys required
    """
    logger.info("="*70)
    logger.info("DOCUMENT PROCESSING VIA MCP DELEGATION")
    logger.info("="*70)

    # Analyze a document
    result = await executor.analyze_document(
        file_path="test_data/sample.pdf",
        questions=[
            "What are the key findings?",
            "What is the budget?",
            "What are the recommendations?"
        ]
    )

    logger.info("\n📄 Document Analysis Results:")
    logger.info(f"Summary: {result['summary']}")
    logger.info(f"Key Findings: {result['key_findings']}")
    logger.info(f"Confidence: {result['confidence_score']}")
    logger.info(f"\n💰 Cost: {result['metadata']['cost']}")
    logger.info(f"🎯 Method: {result['metadata']['execution_method']}")

    return result


async def data_analysis_example():
    """
    Example: Analyze a dataset using MCP-spawned Claude with Agent Skills.

    This demonstrates:
    - Data processing at zero cost
    - Skills for CSV/Excel file handling
    - Progressive skill disclosure
    """
    logger.info("\n" + "="*70)
    logger.info("DATA ANALYSIS VIA MCP DELEGATION")
    logger.info("="*70)

    result = await executor.analyze_dataset(
        data_source="test_data/sample.csv",
        analysis_type="trends"
    )

    logger.info("\n📊 Data Analysis Results:")
    logger.info(f"Trends: {result['trends']}")
    logger.info(f"Anomalies: {result['anomalies']}")
    logger.info(f"Recommendations: {result['recommendations']}")
    logger.info("\n💰 Cost: $0.00 (subscription)")
    logger.info("🎯 Method: MCP delegation")

    return result


async def custom_skill_example():
    """
    Example: Use a custom Agent Skill via MCP delegation.

    This shows how to:
    - Define custom tasks for spawned Claude
    - Use any Agent Skill available
    - Get structured results
    """
    logger.info("\n" + "="*70)
    logger.info("CUSTOM SKILL VIA MCP DELEGATION")
    logger.info("="*70)

    result = await executor.process_with_custom_skill(
        task="Extract all email addresses from the document",
        skill_name="custom_extractor"
    )

    logger.info("\n🔧 Custom Skill Results:")
    logger.info(f"Skill Used: {result['skill_used']}")
    logger.info(f"Output: {result['output']}")
    logger.info(f"Success: {result['success']}")
    logger.info(f"\n💰 Cost: {result['metadata']['cost']}")

    return result


async def progressive_disclosure_example():
    """
    Example: Progressive skill disclosure via MCP delegation.

    This demonstrates:
    - Loading only necessary skills
    - Reducing cognitive load
    - Optimizing performance
    """
    logger.info("\n" + "="*70)
    logger.info("PROGRESSIVE SKILL DISCLOSURE VIA MCP")
    logger.info("="*70)

    result = await executor.progressive_skill_loading(
        user_task="Analyze this PDF report and create a summary",
        available_skills=[
            "pdf_reader",
            "docx_parser",
            "data_processor",
            "image_recognition",
            "web_scraper"
        ]
    )

    logger.info("\n🎯 Progressive Disclosure Results:")
    logger.info(f"Loaded Skills: {result['loaded_skills']}")
    logger.info(f"Skipped Skills: {result['skipped_skills']}")
    logger.info("\nRationale:")
    for skill, reason in result['loading_rationale'].items():
        logger.info(f"  - {skill}: {reason}")
    logger.info("\nMetrics:")
    logger.info(f"  - Load time: {result['metrics']['load_time_ms']}ms")
    logger.info(f"  - Cognitive load reduced: {result['metrics']['cognitive_load_reduced']:.0%}")

    return result


async def cost_comparison():
    """
    Demonstrate cost savings of MCP delegation vs direct API calls.
    """
    logger.info("\n" + "="*70)
    logger.info("COST COMPARISON: MCP vs DIRECT API")
    logger.info("="*70)

    # Simulate processing 100 documents
    num_docs = 100
    avg_tokens = 5000  # per document

    # Direct API cost
    total_tokens = num_docs * avg_tokens
    api_cost = (total_tokens / 1_000_000) * 3.00  # Claude input pricing

    # MCP cost
    mcp_cost = 0.00  # Free on subscription!

    logger.info(f"\nScenario: Process {num_docs} PDF documents")
    logger.info(f"Average tokens per doc: {avg_tokens:,}")
    logger.info(f"Total tokens: {total_tokens:,}")
    logger.info("\n📊 Cost Comparison:")
    logger.info(f"  Direct API calls: ${api_cost:.2f}")
    logger.info(f"  MCP delegation:   ${mcp_cost:.2f}")
    logger.info(f"\n💰 Savings: ${api_cost:.2f} (100%!)")
    logger.info("\n🎉 MCP delegation is FREE and UNLIMITED!")


async def main():
    """
    Run all MCP delegation examples.
    """
    setup_logging()
    load_config()

    print("\n" + "="*70)
    print("BAML + AGENT SKILLS VIA MCP DELEGATION")
    print("Context Foundry Meta-MCP Pattern")
    print("="*70)
    print("\n🎯 ALL operations run on your Claude Code subscription")
    print("💰 NO API costs - completely FREE and UNLIMITED")
    print("🔑 NO API keys needed - inherits Claude Code auth")
    print("⚡ AGENT SKILLS available in all spawned instances")
    print("\n" + "="*70 + "\n")

    # Run examples
    await document_processing_example()
    await data_analysis_example()
    await custom_skill_example()
    await progressive_disclosure_example()
    await cost_comparison()

    print("\n" + "="*70)
    print("KEY TAKEAWAYS")
    print("="*70)
    print("✓ Zero cost - runs on Claude Code subscription")
    print("✓ No API keys needed - inherits authentication")
    print("✓ Full Agent Skills access - PDF, DOCX, data processing")
    print("✓ Fresh 200K context per spawn - no accumulation")
    print("✓ Type-safe with BAML schemas - validation without API calls")
    print("✓ This is the TRUE Context Foundry way!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
