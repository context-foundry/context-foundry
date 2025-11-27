"""
S3 client for Context Foundry pattern and skills library sync.

Provides bidirectional sync between local patterns and AWS S3 community repository.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

logger = logging.getLogger(__name__)


@dataclass
class PatternMetadata:
    """Metadata for a pattern file"""

    pattern_type: str
    version: str
    timestamp: str
    source: str
    item_count: int
    s3_etag: Optional[str] = None
    s3_version_id: Optional[str] = None
    last_synced: Optional[str] = None


class S3PatternClient:
    """
    Client for syncing patterns between local filesystem and S3.

    Features:
    - Bidirectional sync (local ↔ S3)
    - Local caching for offline access
    - Version tracking via S3 versioning
    - Conflict resolution (last-write-wins)
    """

    # Default S3 bucket (can be overridden via env var)
    DEFAULT_BUCKET = "bedrock-builder-kb-898587418237"
    DEFAULT_PREFIX = "community-patterns"

    # Local cache directory
    CACHE_DIR = Path.home() / ".context-foundry" / "patterns"

    # Pattern types
    PATTERN_TYPES = [
        "common-issues",
        "scout-learnings",
        "build-metrics",
        "architecture-patterns",
        "test-patterns",
        "mcp-server-patterns",
    ]

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
        aws_region: str = "us-east-1",
    ):
        """
        Initialize S3 pattern client.

        Args:
            bucket_name: S3 bucket name (defaults to env var or DEFAULT_BUCKET)
            prefix: S3 prefix for patterns (defaults to DEFAULT_PREFIX)
            aws_region: AWS region (defaults to us-east-1)
        """
        self.bucket_name = bucket_name or os.getenv(
            "CONTEXT_FOUNDRY_S3_BUCKET", self.DEFAULT_BUCKET
        )
        self.prefix = prefix or os.getenv(
            "CONTEXT_FOUNDRY_S3_PREFIX", self.DEFAULT_PREFIX
        )
        self.aws_region = aws_region

        if not BOTO3_AVAILABLE:
            logger.warning("boto3 not available - S3 sync disabled")
            self.enabled = False
            return

        try:
            self.s3_client = boto3.client("s3", region_name=aws_region)
            # Test credentials by checking bucket existence
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.enabled = True
            logger.info(f"S3 client initialized: s3://{self.bucket_name}/{self.prefix}")
        except NoCredentialsError:
            logger.warning("AWS credentials not found - S3 sync disabled")
            self.enabled = False
        except ClientError as e:
            logger.warning(f"S3 bucket access error: {e} - S3 sync disabled")
            self.enabled = False

        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_s3_key(self, pattern_type: str) -> str:
        """Generate S3 key for a pattern type"""
        return f"{self.prefix}/{pattern_type}.json"

    def _get_local_path(self, pattern_type: str) -> Path:
        """Generate local file path for a pattern type"""
        return self.CACHE_DIR / f"{pattern_type}.json"

    def _get_metadata_path(self) -> Path:
        """Generate path for sync metadata file"""
        return self.CACHE_DIR / ".s3-sync-metadata.json"

    def _load_sync_metadata(self) -> Dict[str, PatternMetadata]:
        """Load sync metadata from cache"""
        metadata_file = self._get_metadata_path()
        if not metadata_file.exists():
            return {}

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)
                return {k: PatternMetadata(**v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Failed to load sync metadata: {e}")
            return {}

    def _save_sync_metadata(self, metadata: Dict[str, PatternMetadata]):
        """Save sync metadata to cache"""
        try:
            metadata_file = self._get_metadata_path()
            data = {k: asdict(v) for k, v in metadata.items()}
            with open(metadata_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")

    def upload_pattern(
        self,
        pattern_type: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a pattern file from local to S3.

        Args:
            pattern_type: Type of pattern (e.g., "common-issues")
            force: Force upload even if S3 version is newer

        Returns:
            Dict with upload status and metadata
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "S3 client not enabled (check AWS credentials)",
            }

        local_path = self._get_local_path(pattern_type)
        if not local_path.exists():
            return {
                "success": False,
                "error": f"Local pattern file not found: {local_path}",
            }

        # Load local file
        try:
            with open(local_path, "r") as f:
                pattern_data = json.load(f)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read local pattern file: {e}",
            }

        # Check if S3 version is newer (unless force=True)
        if not force:
            # Fetch current S3 metadata to detect conflicts
            try:
                s3_obj = self.s3_client.head_object(
                    Bucket=self.bucket_name, Key=self._get_s3_key(pattern_type)
                )
                s3_last_modified = s3_obj["LastModified"]
                s3_etag = s3_obj.get("ETag")

                # Get local file timestamp
                local_timestamp_str = pattern_data.get("timestamp", "")
                local_modified = (
                    datetime.fromisoformat(local_timestamp_str.replace("Z", "+00:00"))
                    if local_timestamp_str
                    else None
                )

                # Convert S3 LastModified to naive datetime for comparison
                s3_modified_naive = s3_last_modified.replace(tzinfo=None)

                # If S3 version is newer than local, return conflict error
                if local_modified and s3_modified_naive > local_modified:
                    return {
                        "success": False,
                        "error": "Conflict: S3 version is newer than local (use force=True to override)",
                        "conflict": True,
                        "s3_last_modified": s3_last_modified.isoformat(),
                        "local_timestamp": local_timestamp_str,
                        "s3_etag": s3_etag,
                    }
            except self.s3_client.exceptions.NoSuchKey:
                # File doesn't exist in S3 yet, proceed with upload
                pass
            except Exception as e:
                logger.warning(
                    f"Could not check S3 version for conflict detection: {e}"
                )
                # Continue with upload despite error

        # Upload to S3
        s3_key = self._get_s3_key(pattern_type)
        try:
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(pattern_data, indent=2),
                ContentType="application/json",
                Metadata={
                    "pattern-type": pattern_type,
                    "uploaded-at": datetime.utcnow().isoformat(),
                    "source": "context-foundry-local",
                },
            )

            # Update sync metadata
            metadata = self._load_sync_metadata()
            metadata[pattern_type] = PatternMetadata(
                pattern_type=pattern_type,
                version=pattern_data.get("version", "unknown"),
                timestamp=pattern_data.get("timestamp", datetime.utcnow().isoformat()),
                source="local",
                item_count=len(pattern_data.get("patterns", [])),
                s3_etag=response.get("ETag"),
                s3_version_id=response.get("VersionId"),
                last_synced=datetime.utcnow().isoformat(),
            )
            self._save_sync_metadata(metadata)

            return {
                "success": True,
                "pattern_type": pattern_type,
                "s3_key": s3_key,
                "s3_uri": f"s3://{self.bucket_name}/{s3_key}",
                "version_id": response.get("VersionId"),
                "etag": response.get("ETag"),
                "item_count": len(pattern_data.get("patterns", [])),
            }

        except ClientError as e:
            return {
                "success": False,
                "error": f"S3 upload failed: {e}",
            }

    def get_cached_pattern(
        self,
        pattern_type: str,
    ) -> Dict[str, Any]:
        """
        Read pattern from local cache (offline mode).

        This works even when S3 is unavailable or boto3 not installed.

        Args:
            pattern_type: Type of pattern (e.g., "common-issues")

        Returns:
            Dict with cached pattern data or error
        """
        local_path = self._get_local_path(pattern_type)

        if not local_path.exists():
            return {
                "success": False,
                "error": f"No cached pattern found: {local_path}",
                "cache_miss": True,
            }

        try:
            with open(local_path, "r") as f:
                pattern_data = json.load(f)

            return {
                "success": True,
                "pattern_type": pattern_type,
                "local_path": str(local_path),
                "source": "local_cache",
                "item_count": len(pattern_data.get("patterns", [])),
                "data": pattern_data,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read cached pattern: {e}",
            }

    def download_pattern(
        self,
        pattern_type: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Download a pattern file from S3 to local.

        Falls back to cached copy if S3 is unavailable.

        Args:
            pattern_type: Type of pattern (e.g., "common-issues")
            force: Force download even if local version is newer

        Returns:
            Dict with download status and metadata
        """
        if not self.enabled:
            # Fallback: Try to read from local cache
            logger.info(
                f"S3 not enabled, attempting to read from local cache: {pattern_type}"
            )
            cached = self.get_cached_pattern(pattern_type)
            if cached.get("success"):
                cached["offline_mode"] = True
                cached["info"] = "S3 unavailable, using local cache"
            return cached

        s3_key = self._get_s3_key(pattern_type)
        local_path = self._get_local_path(pattern_type)

        # Download from S3
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            pattern_data = json.loads(response["Body"].read())

            # Check if local version is newer (unless force=True)
            if not force and local_path.exists():
                with open(local_path, "r") as f:
                    local_data = json.load(f)

                local_timestamp = local_data.get("timestamp", "")
                s3_timestamp = pattern_data.get("timestamp", "")

                if local_timestamp > s3_timestamp:
                    return {
                        "success": False,
                        "error": "Local version is newer (use force=True to override)",
                        "local_timestamp": local_timestamp,
                        "s3_timestamp": s3_timestamp,
                    }

            # Save to local file
            with open(local_path, "w") as f:
                json.dump(pattern_data, f, indent=2)

            # Update sync metadata
            metadata = self._load_sync_metadata()
            metadata[pattern_type] = PatternMetadata(
                pattern_type=pattern_type,
                version=pattern_data.get("version", "unknown"),
                timestamp=pattern_data.get("timestamp", ""),
                source="s3",
                item_count=len(pattern_data.get("patterns", [])),
                s3_etag=response.get("ETag"),
                s3_version_id=response.get("VersionId"),
                last_synced=datetime.utcnow().isoformat(),
            )
            self._save_sync_metadata(metadata)

            return {
                "success": True,
                "pattern_type": pattern_type,
                "local_path": str(local_path),
                "s3_uri": f"s3://{self.bucket_name}/{s3_key}",
                "version_id": response.get("VersionId"),
                "item_count": len(pattern_data.get("patterns", [])),
            }

        except self.s3_client.exceptions.NoSuchKey:
            return {
                "success": False,
                "error": f"Pattern not found in S3: {s3_key}",
            }
        except ClientError as e:
            return {
                "success": False,
                "error": f"S3 download failed: {e}",
            }

    def list_community_patterns(
        self,
        pattern_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List available patterns in S3.

        Args:
            pattern_type: Filter by pattern type (optional)

        Returns:
            Dict with list of available patterns
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "S3 client not enabled (check AWS credentials)",
            }

        try:
            prefix = f"{self.prefix}/"
            if pattern_type:
                prefix += f"{pattern_type}.json"

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )

            patterns = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                # Skip .initialized.json and other non-pattern files
                if not key.endswith(".json") or key.endswith(".initialized.json"):
                    continue

                # Extract pattern type from key
                pattern_name = key.replace(f"{self.prefix}/", "").replace(".json", "")

                patterns.append(
                    {
                        "pattern_type": pattern_name,
                        "s3_key": key,
                        "s3_uri": f"s3://{self.bucket_name}/{key}",
                        "size_bytes": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"],
                    }
                )

            return {
                "success": True,
                "patterns": patterns,
                "count": len(patterns),
                "bucket": self.bucket_name,
                "prefix": self.prefix,
            }

        except ClientError as e:
            return {
                "success": False,
                "error": f"S3 list failed: {e}",
            }

    def sync_all_patterns(
        self,
        direction: str = "bidirectional",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync all pattern types between local and S3.

        Args:
            direction: "upload", "download", or "bidirectional"
            force: Force sync even if versions conflict

        Returns:
            Dict with sync results for each pattern type
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "S3 client not enabled (check AWS credentials)",
            }

        results = {}

        for pattern_type in self.PATTERN_TYPES:
            if direction in ["upload", "bidirectional"]:
                upload_result = self.upload_pattern(pattern_type, force=force)
                results[f"{pattern_type}_upload"] = upload_result

            if direction in ["download", "bidirectional"]:
                download_result = self.download_pattern(pattern_type, force=force)
                results[f"{pattern_type}_download"] = download_result

        return {
            "success": True,
            "direction": direction,
            "results": results,
        }
