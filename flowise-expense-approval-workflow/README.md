# Flowise Expense Approval Workflow

A comprehensive Flowise AgentFlow v2.2 expense approval workflow that routes expenses to appropriate approvers based on amount thresholds.

## Overview

This workflow automates expense approval by:
1. Accepting expense submissions via a form
2. Validating expense data for completeness and compliance
3. Routing to appropriate approvers based on amount thresholds
4. Processing approval/rejection decisions
5. Notifying submitters of final decisions

## Approval Tiers

| Amount Range | Approver | Review Focus |
|-------------|----------|--------------|
| < $100 | Auto-Approve | Basic compliance check |
| $100 - $499 | Manager | Reasonableness, documentation |
| $500 - $1,999 | Director | Budget impact, value for money |
| $2,000 - $4,999 | VP | Strategic alignment, ROI |
| $5,000+ | Finance Committee | Comprehensive ROI analysis |

## Installation

### Prerequisites

- Flowise v2.2+ installed and running
- Anthropic API Key configured in Flowise

### Import Steps

1. Open Flowise UI
2. Navigate to **Agent Flows** section
3. Click **Add New** or use the import feature
4. Select `expense-approval-workflow.json`
5. Configure the Anthropic API credential:
   - Go to **Credentials** in Flowise
   - Add new **Anthropic API Key** credential
   - Paste your API key

### Configuration

After import, verify:

1. **Anthropic Credential**: All 8 agent nodes should reference your Anthropic API Key credential
2. **Model Selection**: Default is `claude-sonnet-4-5-20250929` (can be changed in each agent)
3. **SearXNG Tool** (optional): If you want web search capabilities, configure the SearXNG tool with your instance URL

## Form Fields

The workflow captures 6 fields from expense submitters:

| Field | Type | Description |
|-------|------|-------------|
| `expenseAmount` | Number | Dollar amount of expense |
| `expenseCategory` | Options | travel, meals, supplies, equipment, other |
| `expenseDescription` | String | Description of expense purpose |
| `receiptAttached` | Boolean | Whether receipt is attached |
| `expenseDate` | String | Date of expense (YYYY-MM-DD) |
| `submitterName` | String | Name of person submitting |

## Validation Rules

The validation agent enforces:

1. Amount must be positive
2. Category must be valid option
3. Description must be >10 characters
4. Receipt required for amounts >$25
5. Date must be valid ISO format, not future
6. Submitter name required

## State Schema

The workflow maintains state through these keys:

```javascript
{
  expense: {
    amount, category, description,
    receipt_attached, date, submitter
  },
  validation: {
    is_valid, errors, validated_at
  },
  approval: {
    status, approver_level,
    decision_rationale, decided_at
  }
}
```

## Testing

### Test Scenarios

| Test | Amount | Expected Route |
|------|--------|----------------|
| Auto-approve small expense | $50 | Auto-Approve -> Notification |
| Manager review | $300 | Manager -> Notification |
| Director review | $1,500 | Director -> Notification |
| VP review | $3,500 | VP -> Notification |
| Finance review | $10,000 | Finance -> Notification |
| Validation failure | Missing receipt | ValidationFail -> Notification |

### Sample Test Inputs

**Auto-Approve Test**
```
Amount: 50
Category: supplies
Description: Office supplies for quarterly planning meeting
Receipt: true
Date: 2024-01-15
Submitter: John Smith
```

**Validation Failure Test**
```
Amount: 500
Category: meals
Description: Lunch
Receipt: false  (should require receipt for >$25)
Date: 2024-01-15
Submitter: Jane Doe
```

## Architecture

### Node Count: 10
- 1 Start Node (Form Input)
- 1 Validation Agent
- 1 Threshold Router (ConditionAgent)
- 6 Approval/Handler Agents
- 1 Notification Agent (Terminal)

### Edge Count: 14
- 2 sequential edges (Start->Validation->Router)
- 6 fan-out edges (Router to each approval tier)
- 6 convergence edges (All approvers to Notification)

### Pattern: Routing with Fan-out/Fan-in

```
Start -> Validate -> Router -+-> Auto ------+
                             +-> Manager ---+
                             +-> Director --+-> Notify
                             +-> VP --------+
                             +-> Finance ---+
                             +-> ValidFail -+
```

## Customization

### Adding Approval Levels

1. Add new scenario to ConditionAgent router
2. Create new approval agent node
3. Add edges from router and to notification
4. Update outputAnchors count on router

### Modifying Thresholds

Edit the `conditionAgentInstructions` in the router node to change dollar thresholds.

### Adding Tools

Each approval agent can have additional tools. Common additions:
- Database lookup for budget checking
- Email integration for escalations
- Slack notification for urgent approvals

## Troubleshooting

### Common Issues

1. **Nodes not rendering**: Ensure all inputParams arrays are complete
2. **Routing incorrect**: Check conditionAgentInstructions thresholds
3. **State not updating**: Verify agentUpdateState key/value pairs
4. **Credential errors**: Confirm Anthropic API Key is configured

### Validation

Run the workflow validator:
```bash
python3 extensions/flowise/validate_workflow.py expense-approval-workflow.json
```

## Files

| File | Purpose |
|------|---------|
| `expense-approval-workflow.json` | Complete Flowise workflow (importable) |
| `WORKFLOW-DIAGRAM.md` | Mermaid diagram visualization |
| `README.md` | This documentation file |

## License

MIT License - See Context Foundry main repository for details.
