# Flowise Expense Approval Workflow

A Flowise AgentFlow v2.2 expense approval workflow that accepts employee expense submissions, validates expense details, routes to appropriate approvers based on amount thresholds ($100-$5000+ tiers), handles approval/rejection responses, and notifies submitters of decisions.

## Features

- **Form-based expense submission** with 6 input fields
- **Automated validation** checking completeness and compliance
- **Tiered approval routing** based on expense amount:
  - Auto-approve for < $100
  - Manager approval for $100-$500
  - Director approval for $500-$2000
  - VP approval for $2000-$5000
  - Finance Committee for > $5000
- **Validation error handling** with helpful feedback
- **Professional notification** of approval decisions

## Prerequisites

- Flowise v2.0+ installed and running
- Anthropic API Key configured as a credential in Flowise

## Installation

### 1. Import the Workflow

1. Open Flowise UI
2. Navigate to **Agentflows** section
3. Click **Add New** or **Import**
4. Upload `expense-approval-workflow.json`

### 2. Configure Credentials

1. Go to **Credentials** in Flowise
2. Add a new **Anthropic API** credential
3. Name it exactly: `Anthropic API Key`
4. Enter your Anthropic API key
5. Save the credential

### 3. Verify Node Configuration

After import, verify each agent node is connected to the `Anthropic API Key` credential:

1. Click on each Agent node
2. Confirm the **Model Configuration** shows the correct credential
3. Save any changes

## Usage

### Submitting an Expense

1. Access the workflow endpoint or chat interface
2. Fill in the expense form:
   - **Expense Amount ($)**: The dollar amount (e.g., 150.00)
   - **Category**: Select from travel, meals, supplies, equipment, other
   - **Description**: Detailed description of the expense (min 10 characters)
   - **Receipt Attached**: Yes/No
   - **Expense Date**: Format YYYY-MM-DD (e.g., 2025-01-15)
   - **Submitter Name**: Your full name

3. Submit the form

### Workflow Processing

1. **Validation**: The system validates:
   - Amount is positive
   - Category is valid
   - Description is meaningful (>10 chars)
   - Receipt attached for amounts > $25
   - Date is valid and not in future
   - Submitter name provided

2. **Routing**: Based on amount:
   | Amount | Approval Path |
   |--------|---------------|
   | < $100 | Auto-approved |
   | $100-$499 | Manager review |
   | $500-$1,999 | Director review |
   | $2,000-$4,999 | VP review |
   | $5,000+ | Finance Committee |

3. **Decision**: Each approver can:
   - **APPROVED**: Expense approved
   - **REJECTED**: Expense rejected with reason
   - **INFO_NEEDED**: Additional information required
   - **ESCALATE**: (Director/VP) Forward to higher authority

4. **Notification**: Final decision sent to submitter

## Workflow Structure

```
Start (Form) -> Validation -> Router -> [Approver Tier] -> Notification
```

**10 Nodes:**
- 1 Start Node (form input)
- 1 Validation Agent
- 1 ConditionAgent Router (6 scenarios)
- 6 Approval/Error Agents
- 1 Notification Agent

**14 Edges:**
- 2 sequential connections
- 6 router fan-out connections
- 6 convergence connections to notification

## Test Scenarios

### Auto-Approve Test ($50)
```json
{
  "expenseAmount": 50,
  "expenseCategory": "supplies",
  "expenseDescription": "Office supplies for the team meeting",
  "receiptAttached": true,
  "expenseDate": "2025-01-10",
  "submitterName": "John Smith"
}
```

### Manager Approval Test ($300)
```json
{
  "expenseAmount": 300,
  "expenseCategory": "travel",
  "expenseDescription": "Taxi fare for client meeting across town",
  "receiptAttached": true,
  "expenseDate": "2025-01-08",
  "submitterName": "Jane Doe"
}
```

### Director Approval Test ($1500)
```json
{
  "expenseAmount": 1500,
  "expenseCategory": "equipment",
  "expenseDescription": "New laptop for development work - approved model",
  "receiptAttached": true,
  "expenseDate": "2025-01-05",
  "submitterName": "Bob Wilson"
}
```

### VP Approval Test ($3500)
```json
{
  "expenseAmount": 3500,
  "expenseCategory": "travel",
  "expenseDescription": "Conference attendance including flights and hotel",
  "receiptAttached": true,
  "expenseDate": "2025-01-15",
  "submitterName": "Alice Johnson"
}
```

### Finance Committee Test ($10000)
```json
{
  "expenseAmount": 10000,
  "expenseCategory": "equipment",
  "expenseDescription": "Server infrastructure upgrade for production environment",
  "receiptAttached": true,
  "expenseDate": "2025-01-20",
  "submitterName": "Tech Lead"
}
```

### Validation Failure Test
```json
{
  "expenseAmount": -50,
  "expenseCategory": "invalid",
  "expenseDescription": "Short",
  "receiptAttached": false,
  "expenseDate": "2030-01-01",
  "submitterName": ""
}
```

## Troubleshooting

### "Model not found" Error
- Ensure the Anthropic API credential is named exactly `Anthropic API Key`
- Verify the credential is properly linked to each agent node

### Validation Always Fails
- Check that the expense date is not in the future
- Ensure description is at least 10 characters
- For amounts > $25, receipt must be attached

### Routing Goes to Wrong Tier
- Verify the expense amount is a valid number
- Check that validation passed (look for "VALID" in validation output)

## Model Configuration

All agents use:
- **Model**: claude-sonnet-4-5-20250929
- **Temperature**: 0.1-0.3 (low for consistency)
- **Streaming**: Enabled

## Files

| File | Description |
|------|-------------|
| `expense-approval-workflow.json` | Complete Flowise workflow (import this) |
| `WORKFLOW-DIAGRAM.md` | Mermaid diagram visualization |
| `README.md` | This documentation |

## Support

For issues with:
- **Flowise**: See [Flowise Documentation](https://docs.flowiseai.com/)
- **Anthropic API**: See [Anthropic Documentation](https://docs.anthropic.com/)
- **This workflow**: Check WORKFLOW-DIAGRAM.md for topology reference
