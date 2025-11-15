"""
Unit tests for S3 Pattern Client

Tests S3 sync functionality with mocked S3 (no live AWS credentials needed).

Requirements:
    - boto3>=1.40.0 (install via: pip install -r requirements-aws.txt)
    - moto[s3]>=5.0.0 (install via: pip install -r requirements-aws.txt)

Run tests:
    pytest tests/test_s3_client.py -v
"""

import json
import pytest
from datetime import datetime, timedelta

# Import S3 client
from context_foundry.storage.s3_client import S3PatternClient, BOTO3_AVAILABLE

# Import moto for S3 mocking
try:
    from moto import mock_aws

    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False


@pytest.fixture
def temp_patterns_dir(tmp_path):
    """Create temporary patterns directory"""
    patterns_dir = tmp_path / ".context-foundry" / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    return patterns_dir


@pytest.fixture
def sample_pattern_data():
    """Sample pattern data for testing"""
    return {
        "version": "2.0",
        "timestamp": datetime.utcnow().isoformat(),
        "source": "test",
        "patterns": [
            {
                "id": "test-pattern-1",
                "issue": "Test issue 1",
                "severity": "medium",
                "solution": "Test solution 1",
            },
            {
                "id": "test-pattern-2",
                "issue": "Test issue 2",
                "severity": "high",
                "solution": "Test solution 2",
            },
        ],
    }


@pytest.fixture
def client_with_mock_s3(temp_patterns_dir, monkeypatch):
    """S3 client with mocked S3 backend (requires boto3 + moto)"""
    if not BOTO3_AVAILABLE:
        pytest.skip(
            "boto3 not available - install via: pip install -r requirements-aws.txt"
        )
    if not MOTO_AVAILABLE:
        pytest.skip(
            "moto not available - install via: pip install -r requirements-aws.txt"
        )

    # Override cache directory
    monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

    with mock_aws():
        # Import boto3 here to use mocked version
        import boto3

        # Create mock S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3.create_bucket(Bucket=bucket_name)

        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )

        # Initialize client with test bucket
        client = S3PatternClient(bucket_name=bucket_name, prefix="test-patterns")

        yield client


class TestS3ClientInitialization:
    """Test S3 client initialization and configuration"""

    def test_client_disabled_without_boto3(self, monkeypatch, temp_patterns_dir):
        """Test client gracefully handles missing boto3 (works without moto)"""
        # Mock boto3 as unavailable
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        client = S3PatternClient()
        assert client.enabled is False

    def test_client_enabled_with_boto3(self, client_with_mock_s3):
        """Test client is enabled when boto3 is available (requires moto)"""
        assert client_with_mock_s3.enabled is True

    def test_client_configuration(self, client_with_mock_s3):
        """Test client configuration (requires moto)"""
        assert client_with_mock_s3.bucket_name == "test-bucket"
        assert client_with_mock_s3.prefix == "test-patterns"
        assert client_with_mock_s3.aws_region == "us-east-1"


class TestS3DisabledBehavior:
    """Test S3 client behavior when AWS is unavailable (works without moto)"""

    def test_upload_fails_gracefully_without_boto3(
        self, monkeypatch, temp_patterns_dir, sample_pattern_data
    ):
        """Test upload returns error when boto3 unavailable"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        # Create local pattern file
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client = S3PatternClient()
        result = client.upload_pattern("common-issues")

        assert result["success"] is False
        assert "not enabled" in result["error"]

    def test_download_fallback_to_cache_without_boto3(
        self, monkeypatch, temp_patterns_dir, sample_pattern_data
    ):
        """Test download falls back to cache when boto3 unavailable"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        # Create cached pattern
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client = S3PatternClient()
        result = client.download_pattern("common-issues")

        assert result["success"] is True
        assert result["source"] == "local_cache"
        assert result["offline_mode"] is True

    def test_list_fails_gracefully_without_boto3(self, monkeypatch, temp_patterns_dir):
        """Test list returns error when boto3 unavailable"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        client = S3PatternClient()
        result = client.list_community_patterns()

        assert result["success"] is False
        assert "not enabled" in result["error"]


class TestUploadPattern:
    """Test pattern upload functionality (requires moto)"""

    def test_upload_pattern_success(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test successful pattern upload"""
        # Create local pattern file
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        # Upload pattern
        result = client_with_mock_s3.upload_pattern("common-issues")

        assert result["success"] is True
        assert result["pattern_type"] == "common-issues"
        assert result["item_count"] == 2
        assert "version_id" in result
        assert "etag" in result

    def test_upload_pattern_file_not_found(self, client_with_mock_s3):
        """Test upload fails when local file doesn't exist"""
        result = client_with_mock_s3.upload_pattern("nonexistent-pattern")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_upload_pattern_conflict_detection(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test conflict detection when S3 version is newer"""
        # Create local pattern file with old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        sample_pattern_data["timestamp"] = old_timestamp
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        # First upload
        client_with_mock_s3.upload_pattern("common-issues")

        # Try to upload again with older local version (without force)
        result = client_with_mock_s3.upload_pattern("common-issues", force=False)

        assert result["success"] is False
        assert "Conflict" in result["error"]
        assert result.get("conflict") is True

    def test_upload_pattern_force_override(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test force upload overrides conflict detection"""
        # Create local pattern file
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        # First upload
        client_with_mock_s3.upload_pattern("common-issues")

        # Second upload with force=True
        result = client_with_mock_s3.upload_pattern("common-issues", force=True)

        assert result["success"] is True

    def test_upload_pattern_s3_disabled(
        self, monkeypatch, temp_patterns_dir, sample_pattern_data
    ):
        """Test upload fails gracefully when S3 is disabled"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        client = S3PatternClient()

        # Create local pattern file
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        result = client.upload_pattern("common-issues")

        assert result["success"] is False
        assert "not enabled" in result["error"]


class TestDownloadPattern:
    """Test pattern download functionality"""

    def test_download_pattern_success(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test successful pattern download"""
        # Upload pattern first
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client_with_mock_s3.upload_pattern("common-issues")

        # Remove local file
        pattern_path.unlink()

        # Download pattern
        result = client_with_mock_s3.download_pattern("common-issues")

        assert result["success"] is True
        assert result["pattern_type"] == "common-issues"
        assert result["item_count"] == 2
        assert pattern_path.exists()

    def test_download_pattern_not_in_s3(self, client_with_mock_s3):
        """Test download fails when pattern doesn't exist in S3"""
        result = client_with_mock_s3.download_pattern("nonexistent-pattern")

        assert result["success"] is False
        assert "not found in S3" in result["error"]

    def test_download_pattern_offline_fallback(
        self, monkeypatch, temp_patterns_dir, sample_pattern_data
    ):
        """Test offline fallback when S3 is unavailable"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        # Create cached pattern file
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client = S3PatternClient()

        # Download should fallback to cache
        result = client.download_pattern("common-issues")

        assert result["success"] is True
        assert result["source"] == "local_cache"
        assert result["offline_mode"] is True
        assert "S3 unavailable" in result["info"]


class TestGetCachedPattern:
    """Test local cache reading functionality (works without moto)"""

    def test_get_cached_pattern_success(
        self, temp_patterns_dir, sample_pattern_data, monkeypatch
    ):
        """Test reading from local cache (works without moto)"""
        # Create cached pattern file
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client = S3PatternClient()
        result = client.get_cached_pattern("common-issues")

        assert result["success"] is True
        assert result["pattern_type"] == "common-issues"
        assert result["source"] == "local_cache"
        assert result["item_count"] == 2
        assert "data" in result

    def test_get_cached_pattern_not_found(self, temp_patterns_dir, monkeypatch):
        """Test cache miss when pattern doesn't exist locally (works without moto)"""
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)
        client = S3PatternClient()
        result = client.get_cached_pattern("nonexistent-pattern")

        assert result["success"] is False
        assert "No cached pattern found" in result["error"]
        assert result.get("cache_miss") is True


class TestListCommunityPatterns:
    """Test listing patterns functionality"""

    def test_list_community_patterns_success(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test listing available patterns"""
        # Upload multiple patterns
        for pattern_type in ["common-issues", "scout-learnings", "test-patterns"]:
            pattern_path = temp_patterns_dir / f"{pattern_type}.json"
            with open(pattern_path, "w") as f:
                json.dump(sample_pattern_data, f)
            client_with_mock_s3.upload_pattern(pattern_type)

        # List patterns
        result = client_with_mock_s3.list_community_patterns()

        assert result["success"] is True
        assert result["count"] == 3
        assert len(result["patterns"]) == 3

        # Verify pattern metadata
        pattern_types = [p["pattern_type"] for p in result["patterns"]]
        assert "common-issues" in pattern_types
        assert "scout-learnings" in pattern_types
        assert "test-patterns" in pattern_types

    def test_list_community_patterns_filtered(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test listing with pattern type filter"""
        # Upload patterns
        for pattern_type in ["common-issues", "scout-learnings"]:
            pattern_path = temp_patterns_dir / f"{pattern_type}.json"
            with open(pattern_path, "w") as f:
                json.dump(sample_pattern_data, f)
            client_with_mock_s3.upload_pattern(pattern_type)

        # List only common-issues
        result = client_with_mock_s3.list_community_patterns(
            pattern_type="common-issues"
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["patterns"][0]["pattern_type"] == "common-issues"

    def test_list_community_patterns_s3_disabled(self, monkeypatch, temp_patterns_dir):
        """Test listing fails gracefully when S3 is disabled"""
        monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
        monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

        client = S3PatternClient()
        result = client.list_community_patterns()

        assert result["success"] is False
        assert "not enabled" in result["error"]


class TestSyncMetadata:
    """Test sync metadata management"""

    def test_sync_metadata_saved_after_upload(
        self, client_with_mock_s3, temp_patterns_dir, sample_pattern_data
    ):
        """Test sync metadata is saved after successful upload"""
        # Create and upload pattern
        pattern_path = temp_patterns_dir / "common-issues.json"
        with open(pattern_path, "w") as f:
            json.dump(sample_pattern_data, f)

        client_with_mock_s3.upload_pattern("common-issues")

        # Check metadata file exists
        metadata_file = temp_patterns_dir / ".s3-sync-metadata.json"
        assert metadata_file.exists()

        # Load and verify metadata
        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        assert "common-issues" in metadata
        assert metadata["common-issues"]["pattern_type"] == "common-issues"
        assert metadata["common-issues"]["item_count"] == 2
        assert "s3_etag" in metadata["common-issues"]
        assert "s3_version_id" in metadata["common-issues"]


# Integration test (can be marked for skip in CI)
@pytest.mark.integration
class TestS3Integration:
    """Integration tests requiring real AWS credentials (skip in CI)"""

    def test_real_s3_upload(self):
        """Test real S3 upload (requires AWS credentials)"""
        # This test is skipped unless explicitly run with --integration flag
        pytest.skip("Integration test - requires real AWS credentials")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
