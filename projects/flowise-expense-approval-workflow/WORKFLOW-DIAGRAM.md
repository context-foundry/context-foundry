# Expense Approval Workflow - Flowise AgentFlow v2.2

## Workflow Topology

```mermaid
flowchart TD
    subgraph Start
        A[startAgentflow_0<br/>Expense Submission Form]
    end

    subgraph Validation
        B[agentAgentflow_validation<br/>Validation Agent]
    end

    subgraph Routing
        C{conditionAgentAgentflow_router<br/>Threshold Router}
    end

    subgraph ApprovalTiers["Approval Tiers"]
        D[agentAgentflow_autoapprove<br/>Auto-Approval Agent<br/>< $100]
        E[agentAgentflow_manager<br/>Manager Approval<br/>$100 - $500]
        F[agentAgentflow_director<br/>Director Approval<br/>$500 - $2000]
        G[agentAgentflow_vp<br/>VP Approval<br/>$2000 - $5000]
        H[agentAgentflow_finance<br/>Finance Committee<br/>> $5000]
        I[agentAgentflow_validationfail<br/>Validation Failed<br/>Error Handler]
    end

    subgraph Terminal
        J[agentAgentflow_notification<br/>Notification Agent]
    end

    A --> B
    B --> C

    C -->|Scenario 0<br/>Amount < $100| D
    C -->|Scenario 1<br/>$100 - $499.99| E
    C -->|Scenario 2<br/>$500 - $1999.99| F
    C -->|Scenario 3<br/>$2000 - $4999.99| G
    C -->|Scenario 4<br/>>= $5000| H
    C -->|Scenario 5<br/>Validation Failed| I

    D --> J
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J

    style A fill:#7C4DFF,color:#fff
    style B fill:#4DD0E1,color:#000
    style C fill:#FF9800,color:#000
    style D fill:#4CAF50,color:#fff
    style E fill:#2196F3,color:#fff
    style F fill:#9C27B0,color:#fff
    style G fill:#E91E63,color:#fff
    style H fill:#FF5722,color:#fff
    style I fill:#F44336,color:#fff
    style J fill:#00BCD4,color:#000
```

## Node Summary

| Node ID | Type | Description | Color |
|---------|------|-------------|-------|
| startAgentflow_0 | Start | Expense submission form with 6 fields | #7C4DFF |
| agentAgentflow_validation | Agent | Validates expense completeness and compliance | #4DD0E1 |
| conditionAgentAgentflow_router | ConditionAgent | Routes based on amount thresholds (6 scenarios) | #FF9800 |
| agentAgentflow_autoapprove | Agent | Auto-approves expenses < $100 | #4CAF50 |
| agentAgentflow_manager | Agent | Manager approval for $100-$500 | #2196F3 |
| agentAgentflow_director | Agent | Director approval for $500-$2000 | #9C27B0 |
| agentAgentflow_vp | Agent | VP approval for $2000-$5000 | #E91E63 |
| agentAgentflow_finance | Agent | Finance Committee for > $5000 | #FF5722 |
| agentAgentflow_validationfail | Agent | Handles validation errors | #F44336 |
| agentAgentflow_notification | Agent | Formats and sends final notification | #00BCD4 |

## Edge Connections (14 total)

### Sequential Flow
1. `startAgentflow_0` -> `agentAgentflow_validation`
2. `agentAgentflow_validation` -> `conditionAgentAgentflow_router`

### Router Fan-out (6 edges)
3. `conditionAgentAgentflow_router` --[0]--> `agentAgentflow_autoapprove`
4. `conditionAgentAgentflow_router` --[1]--> `agentAgentflow_manager`
5. `conditionAgentAgentflow_router` --[2]--> `agentAgentflow_director`
6. `conditionAgentAgentflow_router` --[3]--> `agentAgentflow_vp`
7. `conditionAgentAgentflow_router` --[4]--> `agentAgentflow_finance`
8. `conditionAgentAgentflow_router` --[5]--> `agentAgentflow_validationfail`

### Convergence to Notification (6 edges)
9. `agentAgentflow_autoapprove` -> `agentAgentflow_notification`
10. `agentAgentflow_manager` -> `agentAgentflow_notification`
11. `agentAgentflow_director` -> `agentAgentflow_notification`
12. `agentAgentflow_vp` -> `agentAgentflow_notification`
13. `agentAgentflow_finance` -> `agentAgentflow_notification`
14. `agentAgentflow_validationfail` -> `agentAgentflow_notification`

## Routing Thresholds

| Threshold | Approver Level | Scenario Index |
|-----------|----------------|----------------|
| < $100 | Auto-Approve | 0 |
| $100 - $499.99 | Manager | 1 |
| $500 - $1,999.99 | Director | 2 |
| $2,000 - $4,999.99 | VP | 3 |
| >= $5,000 | Finance Committee | 4 |
| Validation Failed | Error Handler | 5 |

## State Schema

```json
{
  "expense": {
    "amount": "number",
    "category": "string (travel|meals|supplies|equipment|other)",
    "description": "string",
    "receipt_attached": "boolean",
    "date": "string (ISO date)",
    "submitter": "string"
  },
  "validation": {
    "is_valid": "boolean",
    "errors": "array of strings",
    "validated_at": "string (ISO datetime)"
  },
  "approval": {
    "status": "string (pending|approved|rejected|needs_info|validation_failed)",
    "approver_level": "string (auto|manager|director|vp|finance|none)",
    "decision_rationale": "string",
    "decided_at": "string (ISO datetime)"
  }
}
```

## Form Input Fields

1. **expenseAmount** (number): Expense Amount ($)
2. **expenseCategory** (options): Category (travel, meals, supplies, equipment, other)
3. **expenseDescription** (string): Description
4. **receiptAttached** (boolean): Receipt Attached
5. **expenseDate** (string): Expense Date (YYYY-MM-DD)
6. **submitterName** (string): Submitter Name
