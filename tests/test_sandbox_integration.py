"""
Integration tests for Code Sandbox with actual token measurements.

Tests verify real token savings on data filtering workflows.
"""

import json

from sandbox import execute_sandbox_code


def count_tokens(data: any) -> int:
    """
    Estimate token count for data.

    Simple approximation: JSON string length / 4 (OpenAI's rule of thumb).
    This is conservative - actual token count may vary by ~20%.
    """
    json_str = json.dumps(data)
    return len(json_str) // 4


def test_data_filtering_token_savings():
    """Test 1: Large dataset filtering shows measurable token savings"""

    # Create 2,000 row dataset (realistic size that fits in subprocess args)
    large_dataset = [
        {
            "id": i,
            "status": "pending" if i % 2 == 0 else "complete",
            "description": f"Order #{i} - Sample product description with details",
            "amount": i * 1.5,
            "timestamp": f"2025-01-{(i % 28) + 1:02d}T12:00:00Z",
        }
        for i in range(2000)
    ]

    # Token count WITHOUT sandbox (loading all data)
    tokens_without_sandbox = count_tokens(large_dataset)

    # Token count WITH sandbox (filtering to 5 rows)
    result = execute_sandbox_code(
        code="""
filtered = [row for row in data if row['status'] == 'pending']
result = filtered[:5]
""",
        context={"data": large_dataset},
    )

    assert result["success"] is True
    filtered_data = result["result"]
    tokens_with_sandbox = count_tokens(filtered_data)

    # Calculate savings
    reduction_pct = (1 - tokens_with_sandbox / tokens_without_sandbox) * 100

    print("\n" + "=" * 60)
    print("Test 1: Data Filtering Token Savings")
    print("=" * 60)
    print(f"Dataset size: {len(large_dataset):,} rows")
    print(f"Filtered size: {len(filtered_data)} rows")
    print(f"Tokens WITHOUT sandbox: {tokens_without_sandbox:,}")
    print(f"Tokens WITH sandbox: {tokens_with_sandbox:,}")
    print(f"Token reduction: {reduction_pct:.1f}%")
    print("=" * 60)

    # Verify significant savings (>90%)
    assert reduction_pct > 90, f"Expected >90% reduction, got {reduction_pct:.1f}%"
    assert len(filtered_data) == 5


def test_aggregation_token_savings():
    """Test 2: Data aggregation shows measurable token savings"""

    # Create 1,000 transaction records (realistic size)
    transactions = [
        {
            "transaction_id": f"TX-{i:06d}",
            "amount": (i * 7.3) % 1000,  # Varies amounts
            "category": ["food", "transport", "entertainment", "utilities"][i % 4],
            "merchant": f"Merchant #{i % 100}",
            "timestamp": f"2025-01-{(i % 28) + 1:02d}T{i % 24:02d}:00:00Z",
        }
        for i in range(1000)
    ]

    # Token count WITHOUT sandbox
    tokens_without_sandbox = count_tokens(transactions)

    # Token count WITH sandbox (aggregate to summary)
    result = execute_sandbox_code(
        code="""
import statistics

amounts = [float(t['amount']) for t in transactions]

result = {
    'total': sum(amounts),
    'mean': statistics.mean(amounts),
    'median': statistics.median(amounts),
    'count': len(amounts),
    'min': min(amounts),
    'max': max(amounts),
}
""",
        context={"transactions": transactions},
    )

    assert result["success"] is True
    summary = result["result"]
    tokens_with_sandbox = count_tokens(summary)

    # Calculate savings
    reduction_pct = (1 - tokens_with_sandbox / tokens_without_sandbox) * 100

    print("\n" + "=" * 60)
    print("Test 2: Aggregation Token Savings")
    print("=" * 60)
    print(f"Transaction count: {len(transactions):,}")
    print(f"Summary fields: {len(summary)}")
    print(f"Tokens WITHOUT sandbox: {tokens_without_sandbox:,}")
    print(f"Tokens WITH sandbox: {tokens_with_sandbox:,}")
    print(f"Token reduction: {reduction_pct:.1f}%")
    print("=" * 60)

    # Verify massive savings (>99%)
    assert reduction_pct > 99, f"Expected >99% reduction, got {reduction_pct:.1f}%"
    assert summary["count"] == 1000


def test_sampling_token_savings():
    """Test 3: Random sampling shows measurable token savings"""

    # Create 5,000 log entries (realistic size)
    logs = [
        {
            "timestamp": f"2025-01-15T12:{i // 1000:02d}:{i % 60:02d}",
            "level": ["INFO", "DEBUG", "WARNING", "ERROR"][i % 4],
            "message": f"Log message #{i} - Application event occurred",
            "source": f"module{i % 20}",
        }
        for i in range(5000)
    ]

    # Token count WITHOUT sandbox
    tokens_without_sandbox = count_tokens(logs)

    # Token count WITH sandbox (sample 100 entries)
    result = execute_sandbox_code(
        code="""
import random

# Sample 100 random entries
sample = random.sample(logs, k=100)
result = sample
""",
        context={"logs": logs},
    )

    assert result["success"] is True
    sample = result["result"]
    tokens_with_sandbox = count_tokens(sample)

    # Calculate savings
    reduction_pct = (1 - tokens_with_sandbox / tokens_without_sandbox) * 100

    print("\n" + "=" * 60)
    print("Test 3: Sampling Token Savings")
    print("=" * 60)
    print(f"Total logs: {len(logs):,}")
    print(f"Sample size: {len(sample)}")
    print(f"Tokens WITHOUT sandbox: {tokens_without_sandbox:,}")
    print(f"Tokens WITH sandbox: {tokens_with_sandbox:,}")
    print(f"Token reduction: {reduction_pct:.1f}%")
    print("=" * 60)

    # Verify significant savings (>98%)
    assert reduction_pct > 98, f"Expected >98% reduction, got {reduction_pct:.1f}%"
    assert len(sample) == 100


if __name__ == "__main__":
    print("\n🧪 Running Code Sandbox Integration Tests\n")

    test_data_filtering_token_savings()
    test_aggregation_token_savings()
    test_sampling_token_savings()

    print("\n✅ All integration tests passed!\n")
