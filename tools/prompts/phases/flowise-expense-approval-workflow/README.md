# Expense Approval Workflow

A Flowise AgentFlow v2.2 workflow for automated expense approval routing based on amount thresholds.

## Overview

This workflow accepts employee expense submissions via a form input, validates the expense details, routes to the appropriate approver based on amount thresholds, processes the approval decision, and notifies the submitter of the outcome.

## Features

- **Form-based input** for structured expense submission
- **Automatic validation** of expense completeness and compliance
- **Tiered approval routing** based on expense amount:
  - < $100: Auto-approved
  - $100-$500: Manager approval
  - $500-$2,000: Director approval
  - $2,000-$5,000: VP approval
  - > $5,000: Finance Committee approval
- **Validation failure handling** with clear error messages
- **Professional notification** with decision rationale and next steps

## Installation

### Prerequisites

- Flowise v2.2+ installed and running
- Anthropic API Key configured in Flowise credentials

### Import Steps

1. Open your Flowise instance
2. Navigate to **Agentflows** (not regular Chatflows)
3. Click **Add New** → **Import**
4. Upload `expense-approval-workflow.json`
5. Configure the **Anthropic API Key** credential for all agent nodes
6. Save the workflow

### Configure Credentials

Each agent node uses Claude claude-sonnet-4-5-20250929. You'll need to:

1. Go to **Settings** → **Credentials**
2. Add a new **Anthropic API Key** credential
3. Edit each agent node and select your credential

## Usage

### Submitting an Expense

The workflow starts with a form containing these fields:

| Field | Type | Requirements |
|-------|------|--------------|
| Expense Amount ($) | Number | Must be positive |
| Category | Options | travel, meals, supplies, equipment, other |
| Description | String | Required, >10 characters |
| Receipt Attached | Boolean | Required if amount > $25 |
| Expense Date | String | YYYY-MM-DD format, not future |
| Submitter Name | String | Required |

### Example Submission

```
Expense Amount: 350
Category: travel
Description: Flight to NYC for client meeting on March 15th
Receipt Attached: true
Expense Date: 2024-03-15
Submitter Name: John Smith
```

### Expected Responses

**Approved ($350 routes to Manager):**
```
EXPENSE NOTIFICATION

Submitter: John Smith
Expense Amount: $350
Category: travel
Description: Flight to NYC for client meeting on March 15th

Decision: APPROVED
Approval Level: manager

Rationale:
APPROVED: This travel expense for a client meeting is reasonable and
properly documented with a receipt attached. The amount is within
acceptable limits for domestic flights.

Next Steps:
Your expense has been approved and will be reimbursed within 5-7
business days via your standard payment method.
```

## Approval Thresholds

| Amount Range | Approver | Auto Decision |
|--------------|----------|---------------|
| < $100 | Auto-Approval Agent | Yes |
| $100 - $499.99 | Manager | No |
| $500 - $1,999.99 | Director | No |
| $2,000 - $4,999.99 | VP | No |
| ≥ $5,000 | Finance Committee | No |

## Validation Rules

The validation agent checks:

1. **Amount**: Must be a positive number
2. **Category**: Must be one of the valid options
3. **Description**: Required, minimum 10 characters
4. **Receipt**: Required for amounts over $25
5. **Date**: Valid ISO format, cannot be in the future
6. **Submitter**: Required

## Testing

### Test Cases

1. **Auto-Approve Test** ($50 expense)
   - Submit valid expense under $100
   - Expect auto-approval with notification

2. **Manager Approval Test** ($300 expense)
   - Submit valid expense $100-$500
   - Expect manager review and decision

3. **Validation Failure Test**
   - Submit expense without receipt (amount > $25)
   - Expect validation error with guidance

4. **High-Value Test** ($10,000 expense)
   - Submit valid expense > $5,000
   - Expect Finance Committee review

### Running Tests via API

```bash
# Test with Flowise API
curl -X POST http://localhost:3000/api/v1/prediction/<your-flow-id> \
  -H "Content-Type: application/json" \
  -d '{
    "expenseAmount": 75,
    "expenseCategory": "meals",
    "expenseDescription": "Team lunch for project kickoff meeting",
    "receiptAttached": true,
    "expenseDate": "2024-03-20",
    "submitterName": "Jane Doe"
  }'
```

## Architecture

```
Start (Form) → Validation → Threshold Router → [Approval Agent] → Notification
                                ↓
                         6 branches:
                         0: Auto-Approve
                         1: Manager
                         2: Director
                         3: VP
                         4: Finance
                         5: Validation Failed
```

See `WORKFLOW-DIAGRAM.md` for detailed mermaid diagram.

## Customization

### Modify Approval Thresholds

Edit the `conditionAgentAgentflow_router` node's scenarios to change thresholds:

```json
"conditionAgentScenarios": [
  {"scenario": "Auto-Approve: Expense amount is less than $100..."},
  {"scenario": "Manager Approval: Expense amount is $100 to $499.99..."},
  // Modify amounts as needed
]
```

### Add Additional Categories

Edit the `startAgentflow_0` node's form input types to add categories:

```json
{
  "type": "options",
  "label": "Category",
  "name": "expenseCategory",
  "addOptions": [
    {"option": "travel"},
    {"option": "meals"},
    {"option": "supplies"},
    {"option": "equipment"},
    {"option": "software"},  // Add new category
    {"option": "other"}
  ]
}
```

### Customize Approval Criteria

Edit each approval agent's system message to modify review criteria.

## Troubleshooting

### "Credential not found"
- Ensure Anthropic API Key is configured in Flowise credentials
- Re-select credential in each agent node

### Workflow not routing correctly
- Check that validation passes (look for 'VALID' in response)
- Verify amount is being parsed as a number

### State variables not populated
- Ensure previous nodes have `agentUpdateState` configured correctly
- Check variable syntax: `{{ $flow.state.expense.amount }}`

## License

MIT License - Free to use and modify.
