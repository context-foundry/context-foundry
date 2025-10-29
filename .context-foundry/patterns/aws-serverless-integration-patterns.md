# AWS Serverless Integration Patterns - Lessons Learned

## Pattern Category
Infrastructure / AWS Serverless / Integration Debugging

## Context
Deploying complex serverless applications with AWS Step Functions, Lambda, and Bedrock AI models requires careful attention to integration details that are not always obvious from documentation.

## Problem Patterns

### 1. Lambda Return Format Mismatch (Step Functions vs API Gateway)

**Symptom:** Step Functions ChoiceState fails with "Invalid path" error when accessing nested fields
```
Invalid path '$.result.body.field': references an invalid value
```

**Root Cause:** Lambda functions return different formats depending on caller:
- **API Gateway**: Expects `body` as JSON string: `{'statusCode': 200, 'body': json.dumps(data)}`
- **Step Functions**: Expects `body` as object: `{'statusCode': 200, 'body': data}`

**Solution:**
```python
# For Step Functions-only Lambdas
def lambda_handler(event, context):
    result = process_data(event)
    return {
        'statusCode': 200,
        'body': result  # Object, NOT json.dumps(result)
    }

# For API Gateway + Step Functions (dual use)
def lambda_handler(event, context):
    result = process_data(event)
    
    # Detect caller
    if 'requestContext' in event:  # API Gateway
        return {'statusCode': 200, 'body': json.dumps(result)}
    else:  # Step Functions or direct invoke
        return {'statusCode': 200, 'body': result}
```

**Step Functions ResultSelector:**
```typescript
// Option 1: Expect object directly (if Lambda returns object)
resultSelector: {
  'statusCode.$': '$.Payload.statusCode',
  'body.$': '$.Payload.body',  // Already an object
}

// Option 2: Parse JSON string (if Lambda returns json.dumps)
resultSelector: {
  'statusCode.$': '$.Payload.statusCode',
  'body.$': 'States.StringToJson($.Payload.body)',  // Parse JSON string
}
```

**Impact:** Critical - breaks entire workflow
**Detection Time:** Runtime (first execution)
**Fix Time:** 30 minutes (code change + redeploy)

---

### 2. AWS Reserved Environment Variables

**Symptom:** CDK deployment fails with validation error
```
ValidationError: AWS_REGION environment variable is reserved by the lambda runtime 
and can not be set manually
```

**Root Cause:** AWS Lambda automatically provides these environment variables:
- `AWS_REGION` (e.g., "us-east-1")
- `AWS_DEFAULT_REGION`
- `AWS_EXECUTION_ENV`
- `AWS_LAMBDA_FUNCTION_NAME`
- Others (see [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html))

Attempting to override these in CDK/CloudFormation throws validation error.

**Solution:**
```typescript
// ❌ WRONG - Will fail deployment
const environment = {
  AWS_REGION: 'us-east-1',  // Reserved!
};

// ✅ CORRECT - Use custom variable name
const environment = {
  BEDROCK_REGION: this.region,
  APP_AWS_REGION: 'us-east-1',
  // Lambda runtime provides AWS_REGION automatically
};
```

**Python Lambda Code:**
```python
import os

# ✅ Access auto-provided AWS_REGION
region = os.environ.get('AWS_REGION')  # Works - runtime provides it

# ✅ Or use custom variable you control
custom_region = os.environ.get('BEDROCK_REGION', 'us-east-1')
```

**Impact:** Blocks deployment
**Detection Time:** CDK synth/deploy (pre-runtime)
**Fix Time:** 5 minutes

---

### 3. Bedrock Cross-Region Inference Profile IAM Permissions

**Symptom:** Bedrock InvokeModel fails with AccessDeniedException
```
AccessDeniedException: User is not authorized to perform bedrock:InvokeModel 
on resource: arn:aws:bedrock:us-west-2::foundation-model/...
```
Even though IAM policy allows `us-east-1`.

**Root Cause:** Cross-region inference profiles (e.g., `us.anthropic.claude-3-5-sonnet-*`) dynamically route requests to available regions (us-east-1, us-west-2, us-east-2, etc.) for load balancing and availability.

IAM policies scoped to a single region will fail unpredictably depending on routing.

**Solution:**
```typescript
// ❌ WRONG - Region-scoped (will fail on cross-region routing)
resources: [
  `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-*`,
  `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
]

// ✅ CORRECT - Wildcard region for cross-region profiles
resources: [
  `arn:aws:bedrock:*::foundation-model/anthropic.claude-*`,
  `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
]

// Alternative: Explicitly list all US regions
resources: [
  `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-*`,
  `arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-*`,
  `arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-*`,
  ...
]
```

**Model ID Selection:**
```python
# Cross-region inference profile (requires wildcard IAM)
model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

# Region-specific foundation model (requires that specific region in IAM)
model_id = 'anthropic.claude-3-5-sonnet-20241022-v2:0'  
# Note: v2 models REQUIRE inference profiles, cannot use foundation model directly
```

**Impact:** Runtime failures, intermittent (depends on routing)
**Detection Time:** Runtime (first API call)
**Fix Time:** 20 minutes (IAM policy update + propagation)

---

### 4. ECS Fargate Subnet Configuration Discovery

**Symptom:** ECS RunTask fails with subnet validation error
```
InvalidParameterException: The subnet ID 'subnet-xxx' does not exist
```

**Root Cause:** Hardcoded placeholder subnets in code, no automatic subnet discovery.

**Solution:**
```python
# ❌ WRONG - Hardcoded placeholder
subnets = ['subnet-xxx']

# ✅ CORRECT - Environment variable from CDK
subnets = os.environ.get('ECS_SUBNETS', '').split(',')
```

**CDK Stack:**
```typescript
// Option 1: Hardcode specific subnet (simple)
const commonEnv = {
  ECS_SUBNETS: 'subnet-0543825956a935d24',
};

// Option 2: Auto-discover from VPC (better)
import * as ec2 from 'aws-cdk-lib/aws-ec2';

const vpc = ec2.Vpc.fromLookup(this, 'VPC', { isDefault: true });
const subnets = vpc.selectSubnets({
  subnetType: ec2.SubnetType.PUBLIC,
}).subnetIds.join(',');

const commonEnv = {
  ECS_SUBNETS: subnets,
};
```

**Impact:** Blocks ECS task execution
**Detection Time:** Runtime (first ECS task launch)
**Fix Time:** 15 minutes

---

### 5. CDK Asset Hash Detection for Lambda Code Updates

**Symptom:** CDK deploy shows "no changes" even after modifying Lambda code
```
BedrockBuilderAgentStack (no changes)
```

**Root Cause:** CDK uses file hash to detect changes. Sometimes hash doesn't update despite code changes (caching, timestamps, etc.).

**Solution:**

**Option 1: Force Lambda Update (Manual)**
```bash
# Zip and upload directly
cd lambda/my-function
zip -r /tmp/function.zip .
aws lambda update-function-code \
  --function-name my-function \
  --zip-file fileb:///tmp/function.zip
```

**Option 2: Touch Files to Change Hash**
```bash
# Update modification time to force new hash
touch lambda/my-function/handler.py
cdk deploy
```

**Option 3: Add Version/Comment to Force Update**
```typescript
// In CDK stack
const myFunction = new lambda.Function(this, 'MyFunction', {
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/my-function')),
  description: `Updated ${new Date().toISOString()}`,  // Forces update
});
```

**Impact:** Stale code deployed, hard to debug
**Detection Time:** Runtime (unexpected behavior)
**Fix Time:** 10 minutes

---

## Best Practices Summary

### Lambda + Step Functions Integration
1. ✅ Return objects (not JSON strings) for Step Functions-only Lambdas
2. ✅ Use `States.StringToJson()` in ResultSelector if Lambda returns JSON strings
3. ✅ Separate Lambdas for API Gateway vs Step Functions if different return formats needed

### Environment Variables
1. ✅ Never override AWS reserved variables (`AWS_REGION`, `AWS_EXECUTION_ENV`, etc.)
2. ✅ Use custom prefixes (`APP_`, `BEDROCK_`, `MY_SERVICE_`) for your variables
3. ✅ Document which variables are auto-provided vs custom in your README

### Bedrock IAM Permissions
1. ✅ Use wildcard regions (`*`) for cross-region inference profiles
2. ✅ Explicitly list regions if security policy requires (all US regions)
3. ✅ Understand model routing: inference profiles span regions, foundation models are region-specific

### Infrastructure as Code
1. ✅ Use environment variables for configuration (subnets, regions, endpoints)
2. ✅ Auto-discover resources when possible (VPC subnets, security groups)
3. ✅ Avoid hardcoded placeholders in production code
4. ✅ Force CDK updates with manual Lambda code deployment if hash detection fails

---

## Detection Checklist

Before deploying serverless integrations:

- [ ] Verify Lambda return format matches caller expectations (API GW vs Step Functions)
- [ ] Check no AWS reserved env vars are being overridden
- [ ] Confirm IAM policies allow cross-region access if using inference profiles
- [ ] Replace all hardcoded placeholders (subnets, IDs) with env vars
- [ ] Test Step Functions JSONPath expressions with actual Lambda output
- [ ] Validate CDK asset hash updates with a dummy code change

---

## Related Patterns
- [AWS Step Functions Best Practices](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)
- [Lambda Environment Variables](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html)
- [Bedrock Inference Profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

---

## Pattern Metadata
- **Source Project:** bedrock-agentic-builder (Phase 2 deployment)
- **Date Captured:** 2025-10-28
- **Contributors:** Claude Code + User (debugging session)
- **Severity:** High (each issue blocked deployment/runtime)
- **Frequency:** Common (affects most Step Functions + Lambda integrations)
- **Tags:** #aws #serverless #stepfunctions #lambda #bedrock #iam #debugging
