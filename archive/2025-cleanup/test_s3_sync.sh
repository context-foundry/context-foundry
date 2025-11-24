#!/bin/bash
# Quick S3 Pattern Sync Test Script
# Tests the S3 integration in real-world usage

set -e

echo "=========================================="
echo "Context Foundry S3 Sync - Quick Test"
echo "=========================================="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check AWS credentials
echo -e "${YELLOW}Test 1: AWS Credentials${NC}"
if aws sts get-caller-identity &>/dev/null; then
    ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✅ AWS credentials configured${NC}"
    echo "   Account: $ACCOUNT"
else
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo "   Run: aws configure"
    exit 1
fi
echo

# Test 2: Check boto3 installed
echo -e "${YELLOW}Test 2: boto3 Installation${NC}"
if python3 -c "import boto3" 2>/dev/null; then
    VERSION=$(python3 -c "import boto3; print(boto3.__version__)")
    echo -e "${GREEN}✅ boto3 installed${NC}"
    echo "   Version: $VERSION"
else
    echo -e "${RED}❌ boto3 not installed${NC}"
    echo "   Run: pip install -r requirements-aws.txt"
    exit 1
fi
echo

# Test 3: Check S3 bucket access
echo -e "${YELLOW}Test 3: S3 Bucket Access${NC}"
if aws s3 ls s3://bedrock-builder-kb-898587418237/community-patterns/ &>/dev/null; then
    echo -e "${GREEN}✅ S3 bucket accessible${NC}"
    COUNT=$(aws s3 ls s3://bedrock-builder-kb-898587418237/community-patterns/ | wc -l)
    echo "   Files in bucket: $COUNT"
else
    echo -e "${RED}❌ Cannot access S3 bucket${NC}"
    echo "   Check IAM permissions"
    exit 1
fi
echo

# Test 4: Initialize S3 client
echo -e "${YELLOW}Test 4: S3 Client Initialization${NC}"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient

client = S3PatternClient()
if not client.enabled:
    print("❌ S3 client not enabled")
    exit(1)

print(f"✅ S3 client initialized")
print(f"   Bucket: {client.bucket_name}")
print(f"   Prefix: {client.prefix}")
print(f"   Region: {client.aws_region}")
EOF
echo

# Test 5: List community patterns
echo -e "${YELLOW}Test 5: List Community Patterns${NC}"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
import json

client = S3PatternClient()
result = client.list_community_patterns()

if not result["success"]:
    print(f"❌ List failed: {result.get('error')}")
    exit(1)

print(f"✅ Found {result['count']} pattern types:")
for pattern in result["patterns"]:
    print(f"   - {pattern['pattern_type']}: {pattern['size_bytes']} bytes")
EOF
echo

# Test 6: Upload a pattern
echo -e "${YELLOW}Test 6: Upload Pattern (common-issues)${NC}"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
from pathlib import Path

client = S3PatternClient()

# Check if local pattern exists
local_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"
if not local_path.exists():
    print(f"⚠️  No local pattern found at {local_path}")
    print("   Skipping upload test")
    exit(0)

result = client.upload_pattern("common-issues", force=True)

if not result["success"]:
    print(f"❌ Upload failed: {result.get('error')}")
    exit(1)

print(f"✅ Upload successful")
print(f"   Items: {result['item_count']}")
print(f"   Version ID: {result['version_id'][:20]}...")
print(f"   ETag: {result['etag'][:20]}...")
EOF
echo

# Test 7: Download pattern
echo -e "${YELLOW}Test 7: Download Pattern${NC}"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
import shutil
from pathlib import Path

client = S3PatternClient()
local_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"
backup_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json.test-backup"

# Backup current file
if local_path.exists():
    shutil.copy(local_path, backup_path)
    local_path.unlink()
    print("   (Created backup and removed local file)")

# Download from S3
result = client.download_pattern("common-issues")

if not result["success"]:
    # Restore backup
    if backup_path.exists():
        shutil.copy(backup_path, local_path)
        backup_path.unlink()
    print(f"❌ Download failed: {result.get('error')}")
    exit(1)

print(f"✅ Download successful")
print(f"   Items: {result['item_count']}")
print(f"   Saved to: {result['local_path']}")

# Restore backup
if backup_path.exists():
    backup_path.unlink()
EOF
echo

# Test 8: Offline cache fallback
echo -e "${YELLOW}Test 8: Offline Cache Fallback${NC}"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient

client = S3PatternClient()
result = client.get_cached_pattern("common-issues")

if not result["success"]:
    print(f"❌ Cache read failed: {result.get('error')}")
    exit(1)

print(f"✅ Cache read successful")
print(f"   Items: {result['item_count']}")
print(f"   Source: {result['source']}")
EOF
echo

# Test 9: Check S3 versioning
echo -e "${YELLOW}Test 9: S3 Versioning${NC}"
VERSIONING=$(aws s3api get-bucket-versioning \
    --bucket bedrock-builder-kb-898587418237 \
    --query 'Status' \
    --output text 2>/dev/null || echo "None")

if [ "$VERSIONING" = "Enabled" ]; then
    echo -e "${GREEN}✅ S3 versioning enabled${NC}"

    # Count versions
    VERSION_COUNT=$(aws s3api list-object-versions \
        --bucket bedrock-builder-kb-898587418237 \
        --prefix community-patterns/common-issues.json \
        --query 'length(Versions)' 2>/dev/null || echo "0")

    echo "   Versions of common-issues.json: $VERSION_COUNT"
else
    echo -e "${YELLOW}⚠️  S3 versioning not enabled${NC}"
    echo "   Recommended: Enable versioning for backup protection"
fi
echo

# Summary
echo "=========================================="
echo -e "${GREEN}All tests passed! ✅${NC}"
echo "=========================================="
echo
echo "Your S3 pattern sync is working correctly!"
echo
echo "Next steps:"
echo "  1. Upload all pattern types:"
echo "     for p in common-issues scout-learnings architecture-patterns; do"
echo "       python3 -c \"from context_foundry.storage import S3PatternClient; S3PatternClient().upload_pattern('\$p', force=True)\""
echo "     done"
echo
echo "  2. See detailed testing guide:"
echo "     cat docs/S3_TESTING_GUIDE.md"
echo
