# Real-World Testing Guide for S3 Pattern Sync

## Prerequisites

1. **AWS Credentials Configured**
   ```bash
   # Verify AWS credentials are set up
   aws sts get-caller-identity

   # Should return your AWS account info
   # If not, run: aws configure
   ```

2. **Install AWS Dependencies**
   ```bash
   cd ~/homelab/context-foundry
   pip install -r requirements-aws.txt
   ```

3. **Verify S3 Bucket Access**
   ```bash
   # Check you can access the bucket
   aws s3 ls s3://bedrock-builder-kb-898587418237/community-patterns/
   ```

---

## Test 1: Upload Your Local Patterns to S3

### Step 1: Check What Patterns You Have Locally
```bash
ls -lh ~/.context-foundry/patterns/
# You should see files like:
# - common-issues.json
# - scout-learnings.json
# - architecture-patterns.json
# etc.
```

### Step 2: Upload a Pattern via Python
```bash
python3 << 'EOF'
from context_foundry.storage import S3PatternClient

# Initialize client
client = S3PatternClient()
print(f"S3 client enabled: {client.enabled}")
print(f"Bucket: {client.bucket_name}")
print()

# Upload common-issues pattern
print("Uploading common-issues...")
result = client.upload_pattern("common-issues")

if result["success"]:
    print("✅ Upload successful!")
    print(f"   - Items: {result['item_count']}")
    print(f"   - Version ID: {result['version_id']}")
    print(f"   - ETag: {result['etag']}")
else:
    print(f"❌ Upload failed: {result['error']}")
EOF
```

### Step 3: Verify Upload in S3
```bash
# List patterns in S3
aws s3 ls s3://bedrock-builder-kb-898587418237/community-patterns/

# Get detailed info
aws s3api head-object \
  --bucket bedrock-builder-kb-898587418237 \
  --key community-patterns/common-issues.json
```

---

## Test 2: List Community Patterns

```bash
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
import json

client = S3PatternClient()
result = client.list_community_patterns()

if result["success"]:
    print(f"Found {result['count']} patterns in S3:\n")
    for pattern in result["patterns"]:
        print(f"  - {pattern['pattern_type']}")
        print(f"    Size: {pattern['size_bytes']} bytes")
        print(f"    Items: {pattern['item_count']}")
        print(f"    Last Modified: {pattern['last_modified']}")
        print()
else:
    print(f"❌ List failed: {result['error']}")
EOF
```

---

## Test 3: Download Patterns from S3

### Scenario: Download to a fresh machine (or delete local copy first)

```bash
# Backup your local pattern
cp ~/.context-foundry/patterns/common-issues.json ~/.context-foundry/patterns/common-issues.json.backup

# Delete local copy to simulate fresh machine
rm ~/.context-foundry/patterns/common-issues.json

# Download from S3
python3 << 'EOF'
from context_foundry.storage import S3PatternClient

client = S3PatternClient()
result = client.download_pattern("common-issues")

if result["success"]:
    print("✅ Download successful!")
    print(f"   - Items: {result['item_count']}")
    print(f"   - Saved to: {result['local_path']}")
else:
    print(f"❌ Download failed: {result['error']}")
EOF

# Verify file was restored
ls -lh ~/.context-foundry/patterns/common-issues.json
```

---

## Test 4: Conflict Detection

### Scenario: Prevent overwriting newer S3 version

```bash
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
import json
from datetime import datetime, timedelta
from pathlib import Path

client = S3PatternClient()

# Upload current version first
print("Step 1: Upload current version to S3...")
result1 = client.upload_pattern("common-issues")
print(f"   ✅ Uploaded: {result1.get('success')}")
print()

# Modify local file with OLD timestamp (simulate stale local copy)
print("Step 2: Modify local file with old timestamp...")
local_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"
with open(local_path, "r") as f:
    data = json.load(f)

# Set timestamp to 1 day ago
old_time = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
data["timestamp"] = old_time

with open(local_path, "w") as f:
    json.dump(data, f, indent=2)
print(f"   ✅ Set local timestamp to: {old_time}")
print()

# Try to upload without force - should fail with conflict
print("Step 3: Try to upload old version (should fail)...")
result2 = client.upload_pattern("common-issues", force=False)
if result2.get("conflict"):
    print("   ✅ Conflict detected correctly!")
    print(f"   - Error: {result2['error']}")
    print(f"   - S3 modified: {result2['s3_last_modified']}")
    print(f"   - Local timestamp: {result2['local_timestamp']}")
else:
    print(f"   ❌ Should have detected conflict: {result2}")
print()

# Upload with force=True - should succeed
print("Step 4: Upload with force=True (should succeed)...")
result3 = client.upload_pattern("common-issues", force=True)
if result3["success"]:
    print("   ✅ Force upload succeeded!")
    print(f"   - New version ID: {result3['version_id']}")
else:
    print(f"   ❌ Force upload failed: {result3['error']}")
EOF
```

---

## Test 5: Offline Fallback

### Scenario: System works without AWS access

```bash
# Test 1: Read from cache when S3 disabled
python3 << 'EOF'
from context_foundry.storage import S3PatternClient

# Simulate S3 unavailable
client = S3PatternClient()

# Get cached pattern (works even if S3 is down)
result = client.get_cached_pattern("common-issues")

if result["success"]:
    print("✅ Offline cache read successful!")
    print(f"   - Source: {result['source']}")
    print(f"   - Items: {result['item_count']}")
    print(f"   - Path: {result['local_path']}")
else:
    print(f"❌ Cache read failed: {result['error']}")
EOF

# Test 2: Download falls back to cache when S3 unavailable
# (We'll test by temporarily breaking AWS credentials)
python3 << 'EOF'
import os
from context_foundry.storage import S3PatternClient

# Temporarily break AWS access
old_profile = os.environ.get("AWS_PROFILE")
os.environ["AWS_PROFILE"] = "nonexistent-profile"

client = S3PatternClient()

# Try to download - should fallback to cache
result = client.download_pattern("common-issues")

# Restore AWS profile
if old_profile:
    os.environ["AWS_PROFILE"] = old_profile
else:
    os.environ.pop("AWS_PROFILE", None)

if result["success"] and result.get("offline_mode"):
    print("✅ Offline fallback worked!")
    print(f"   - Source: {result['source']}")
    print(f"   - Info: {result.get('info')}")
else:
    print(f"Result: {result}")
EOF
```

---

## Test 6: Auto-Sync During Pattern Merge

### Scenario: Pattern merge automatically syncs to S3

```bash
# Create a fake project with patterns
mkdir -p /tmp/test-project/.context-foundry/patterns
cat > /tmp/test-project/.context-foundry/patterns/common-issues.json << 'EOF'
{
  "version": "2.0",
  "timestamp": "2025-11-15T10:00:00Z",
  "source": "test-project",
  "patterns": [
    {
      "id": "test-pattern-from-project",
      "issue": "Test issue from project",
      "severity": "medium",
      "solution": "Test solution",
      "frequency": 1,
      "project_types": ["test"],
      "last_seen": "2025-11-15T10:00:00Z"
    }
  ]
}
EOF

# Merge the project patterns (should auto-sync to S3)
python3 << 'EOF'
from tools.mcp_utils.pattern_management import merge_project_patterns_impl
import json

result = merge_project_patterns_impl(
    project_pattern_file="/tmp/test-project/.context-foundry/patterns/common-issues.json",
    pattern_type="common-issues",
    increment_build_count=False
)

print("Merge result:")
print(json.dumps(result, indent=2))

# Check if S3 sync happened
if "s3_sync" in result:
    print("\n✅ Auto-sync to S3:")
    if result["s3_sync"]["success"]:
        print(f"   - Synced successfully")
        print(f"   - Version ID: {result['s3_sync'].get('version_id')}")
    else:
        print(f"   - Sync failed: {result['s3_sync'].get('error')}")
else:
    print("\n⚠️  No S3 sync info (boto3 may not be installed)")
EOF

# Clean up
rm -rf /tmp/test-project
```

---

## Test 7: Using MCP Tools (If MCP Server is Running)

If you're using the Context Foundry MCP server with Claude Code:

### In Claude Code, ask:
```
Can you sync my local common-issues patterns to S3?
```

### Claude Code will call:
```python
sync_patterns_to_s3("common-issues")
```

### To list patterns:
```
Can you show me what community patterns are available in S3?
```

### Claude Code will call:
```python
list_s3_community_patterns()
```

### To download:
```
Can you download the latest architecture-patterns from S3?
```

### Claude Code will call:
```python
pull_patterns_from_s3("architecture-patterns")
```

---

## Test 8: S3 Versioning Recovery

### Scenario: Recover from accidental overwrite

```bash
# List all versions of a pattern
aws s3api list-object-versions \
  --bucket bedrock-builder-kb-898587418237 \
  --prefix community-patterns/common-issues.json

# This will show all version IDs

# Download a specific version
aws s3api get-object \
  --bucket bedrock-builder-kb-898587418237 \
  --key community-patterns/common-issues.json \
  --version-id <VERSION_ID_HERE> \
  ~/.context-foundry/patterns/common-issues-recovered.json

# Compare versions
diff ~/.context-foundry/patterns/common-issues.json \
     ~/.context-foundry/patterns/common-issues-recovered.json
```

---

## Test 9: Cost Monitoring

```bash
# Check S3 storage usage
aws s3api list-objects-v2 \
  --bucket bedrock-builder-kb-898587418237 \
  --prefix community-patterns/ \
  --query 'sum(Contents[].Size)' \
  --output text | awk '{print $1/1024/1024 " MB"}'

# Count number of versions (affects storage cost)
aws s3api list-object-versions \
  --bucket bedrock-builder-kb-898587418237 \
  --prefix community-patterns/ \
  --query 'length(Versions)'
```

---

## Troubleshooting Real-World Issues

### Issue: "S3 client not enabled"
```bash
# Check if boto3 is installed
python3 -c "import boto3; print(boto3.__version__)"

# If not installed:
pip install -r requirements-aws.txt
```

### Issue: "NoCredentialsError"
```bash
# Check AWS credentials
aws sts get-caller-identity

# If fails, configure:
aws configure
```

### Issue: "AccessDenied" errors
```bash
# Check your IAM permissions
aws s3api head-bucket --bucket bedrock-builder-kb-898587418237

# You need these permissions:
# - s3:ListBucket
# - s3:GetObject
# - s3:PutObject
# - s3:GetObjectVersion
# - s3:ListBucketVersions
```

### Issue: Upload succeeds but no version ID returned
```bash
# Check if versioning is enabled
aws s3api get-bucket-versioning \
  --bucket bedrock-builder-kb-898587418237

# Should return: "Status": "Enabled"
# If not, enable it:
aws s3api put-bucket-versioning \
  --bucket bedrock-builder-kb-898587418237 \
  --versioning-configuration Status=Enabled
```

---

## Complete End-to-End Test Script

Save this as `test_s3_sync.sh`:

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "Context Foundry S3 Sync - E2E Test"
echo "=========================================="
echo

# Test 1: Client initialization
echo "Test 1: S3 Client Initialization"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
assert client.enabled, "S3 client should be enabled"
print("✅ S3 client initialized")
EOF
echo

# Test 2: Upload pattern
echo "Test 2: Upload Pattern"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
result = client.upload_pattern("common-issues", force=True)
assert result["success"], f"Upload failed: {result.get('error')}"
print(f"✅ Uploaded {result['item_count']} patterns")
EOF
echo

# Test 3: List patterns
echo "Test 3: List Patterns"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
result = client.list_community_patterns()
assert result["success"], f"List failed: {result.get('error')}"
assert result["count"] > 0, "Should have at least 1 pattern"
print(f"✅ Found {result['count']} patterns in S3")
EOF
echo

# Test 4: Download pattern
echo "Test 4: Download Pattern"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
result = client.download_pattern("common-issues", force=True)
assert result["success"], f"Download failed: {result.get('error')}"
print(f"✅ Downloaded {result['item_count']} patterns")
EOF
echo

# Test 5: Offline cache
echo "Test 5: Offline Cache"
python3 << 'EOF'
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
result = client.get_cached_pattern("common-issues")
assert result["success"], f"Cache read failed: {result.get('error')}"
print(f"✅ Read {result['item_count']} patterns from cache")
EOF
echo

echo "=========================================="
echo "All tests passed! ✅"
echo "=========================================="
```

Run it:
```bash
chmod +x test_s3_sync.sh
./test_s3_sync.sh
```

---

## Expected Output

When everything is working correctly, you should see:

```
==========================================
Context Foundry S3 Sync - E2E Test
==========================================

Test 1: S3 Client Initialization
✅ S3 client initialized

Test 2: Upload Pattern
✅ Uploaded 27 patterns

Test 3: List Patterns
✅ Found 5 patterns in S3

Test 4: Download Pattern
✅ Downloaded 27 patterns

Test 5: Offline Cache
✅ Read 27 patterns from cache

==========================================
All tests passed! ✅
==========================================
```

---

## Next Steps

After successful testing:

1. **Upload all pattern types:**
   ```bash
   for pattern in common-issues scout-learnings architecture-patterns test-patterns mcp-server-patterns; do
     python3 -c "from context_foundry.storage import S3PatternClient; \
       client = S3PatternClient(); \
       result = client.upload_pattern('$pattern', force=True); \
       print(f'$pattern: {result.get(\"success\")}')"
   done
   ```

2. **Set up billing alarm:**
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name context-foundry-s3-costs \
     --alarm-description "Alert if S3 costs exceed $5/month" \
     --metric-name EstimatedCharges \
     --namespace AWS/Billing \
     --statistic Maximum \
     --period 86400 \
     --evaluation-periods 1 \
     --threshold 5 \
     --comparison-operator GreaterThanThreshold
   ```

3. **Monitor costs weekly:**
   ```bash
   # Check current month's charges
   aws ce get-cost-and-usage \
     --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
     --granularity MONTHLY \
     --metrics BlendedCost \
     --filter file://<(echo '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Simple Storage Service"]}}')
   ```

---

*Last Updated: 2025-11-15*
