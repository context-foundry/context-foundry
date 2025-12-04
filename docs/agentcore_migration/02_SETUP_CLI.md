# AWS Bedrock AgentCore Setup: CLI Guide

This guide details how to provision the necessary AWS Bedrock AgentCore resources using the **AWS CLI**. This is the preferred method for reproducibility and automation.

## 📋 Prerequisites
*   AWS CLI installed (`aws --version`)
*   AWS Credentials configured (`aws configure`)
*   Permissions to create IAM Roles, Lambda functions, and Bedrock Agents.

## 1. Create IAM Role for the Agent
The agent needs permission to call Bedrock models.

```bash
# 1. Create Trust Policy
cat <<EOF > agent-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# 2. Create Role
aws iam create-role \
    --role-name ContextFoundryAgentRole \
    --assume-role-policy-document file://agent-trust-policy.json

# 3. Attach Bedrock Full Access (Or scope down for production)
aws iam attach-role-policy \
    --role-name ContextFoundryAgentRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
```

## 2. Create the Agent
Now we create the "Brain".

```bash
aws bedrock-agent create-agent \
    --agent-name "ContextFoundry-Builder" \
    --agent-resource-role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/ContextFoundryAgentRole \
    --foundation-model "anthropic.claude-3-sonnet-20240229-v1:0" \
    --instruction "You are an expert software architect and builder. Your goal is to plan and write code for software projects based on user specifications." \
    --agent-collaboration "SUPERVISOR"
```
*Note: Replace `YOUR_ACCOUNT_ID` with your actual AWS Account ID.*

## 3. Create Action Group (The "Hands")
To give the agent "hands" (file access), we define an **Action Group**. In the AgentCore model, this usually maps to a Lambda function or an OpenAPI schema.

For **Context Foundry**, since we want to write files to *your local machine*, we have two options:
1.  **Lambda Proxy:** A Lambda that sends commands to your local daemon via a secure tunnel (ngrok).
2.  **Polling:** Your local daemon polls the agent for "pending actions" (if supported) or we use a simplified "Return Control" flow.

*For this setup, we will define the Schema first.*

```bash
# create-action-group.json
{
    "actionGroupName": "LocalFileTools",
    "actionGroupExecutor": {
        "lambda": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:ContextFoundryBridge"
    },
    "apiSchema": {
        "payload": "{\"openapi\":\"3.0.0\",\"paths\":{\"/write_file\":{\"post\":{...}}}}" 
    }
}
```

```bash
aws bedrock-agent create-agent-action-group \
    --agent-id "AGENT_ID_FROM_STEP_2" \
    --agent-version "DRAFT" \
    --action-group-name "LocalFileTools" \
    --cli-input-json file://create-action-group.json
```

## 4. Prepare the Agent
After creating or modifying, you must "prepare" the agent to package the changes.

```bash
aws bedrock-agent prepare-agent \
    --agent-id "AGENT_ID_FROM_STEP_2"
```

## 5. Create an Alias (Deployment)
Aliases represent stable versions (e.g., "Prod", "Test").

```bash
aws bedrock-agent create-agent-alias \
    --agent-id "AGENT_ID_FROM_STEP_2" \
    --agent-alias-name "Development"
```

## ✅ Verification
You can now invoke the agent via CLI:

```bash
aws bedrock-agent-runtime invoke-agent \
    --agent-id "AGENT_ID" \
    --agent-alias-id "ALIAS_ID" \
    --session-id "test-session-001" \
    --input-text "Create a plan for a snake game."
```
