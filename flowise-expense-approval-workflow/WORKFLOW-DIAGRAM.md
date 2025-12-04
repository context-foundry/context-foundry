# Expense Approval Workflow - Visual Diagram

## Workflow Topology

```mermaid
flowchart TD
    subgraph Input["Input Layer"]
        START[("Start\n(Form Input)")]
    end

    subgraph Validation["Validation Layer"]
        VAL["Agent.Validation\n(Expense Validator)"]
    end

    subgraph Routing["Routing Layer"]
        ROUTER{"Threshold Router\n(ConditionAgent)"}
    end

    subgraph ApprovalTiers["Approval Tiers"]
        AUTO["Agent.AutoApprove\n(<$100)"]
        MGR["Agent.Manager\n($100-$500)"]
        DIR["Agent.Director\n($500-$2000)"]
        VP["Agent.VP\n($2000-$5000)"]
        FIN["Agent.Finance\n(>$5000)"]
        FAIL["Agent.ValidationFail\n(Invalid)"]
    end

    subgraph Output["Output Layer"]
        NOTIFY["Agent.Notification\n(Terminal)"]
    end

    START -->|submit| VAL
    VAL -->|validated| ROUTER

    ROUTER -->|"Scenario 0: <$100"| AUTO
    ROUTER -->|"Scenario 1: $100-$500"| MGR
    ROUTER -->|"Scenario 2: $500-$2000"| DIR
    ROUTER -->|"Scenario 3: $2000-$5000"| VP
    ROUTER -->|"Scenario 4: >$5000"| FIN
    ROUTER -->|"Scenario 5: INVALID"| FAIL

    AUTO -->|notify| NOTIFY
    MGR -->|notify| NOTIFY
    DIR -->|notify| NOTIFY
    VP -->|notify| NOTIFY
    FIN -->|notify| NOTIFY
    FAIL -->|notify| NOTIFY

    style START fill:#7EE787,stroke:#333,color:#000
    style VAL fill:#4DD0E1,stroke:#333,color:#000
    style ROUTER fill:#ff8fab,stroke:#333,color:#000
    style AUTO fill:#66BB6A,stroke:#333,color:#000
    style MGR fill:#4DD0E1,stroke:#333,color:#000
    style DIR fill:#4DD0E1,stroke:#333,color:#000
    style VP fill:#4DD0E1,stroke:#333,color:#000
    style FIN fill:#FFB74D,stroke:#333,color:#000
    style FAIL fill:#FF6B6B,stroke:#333,color:#000
    style NOTIFY fill:#66BB6A,stroke:#333,color:#000
```

## Workflow Statistics

| Metric | Value |
|--------|-------|
| Total Nodes | 10 |
| Total Edges | 14 |
| Pattern Type | Routing (Fan-out) |
| Approval Tiers | 5 |
| Decision Paths | 6 |

## Node Details

### Start Node
- **Type**: Start (Form Input)
- **Form Fields**: 6 (Amount, Category, Description, Receipt, Date, Submitter)
- **State Initialization**: 11 keys

### Validation Agent
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.1
- **Validation Rules**: 6 checks
- **Tools**: currentDateTime

### Threshold Router (ConditionAgent)
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.1
- **Output Scenarios**: 6

### Approval Agents

| Agent | Threshold | Color | Tools |
|-------|-----------|-------|-------|
| AutoApprove | <$100 | Green | currentDateTime |
| Manager | $100-$500 | Cyan | currentDateTime, searXNG |
| Director | $500-$2000 | Cyan | currentDateTime, searXNG |
| VP | $2000-$5000 | Cyan | currentDateTime, searXNG |
| Finance | >$5000 | Orange | currentDateTime, searXNG |
| ValidationFail | Invalid | Red | currentDateTime |

### Notification Agent (Terminal)
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.3
- **Memory**: Enabled
- **Response Type**: Assistant Message

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
    "is_valid": "string",
    "errors": "string",
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

## Routing Thresholds Summary

```
Amount Range      | Approver Level   | Scenario Index
------------------|------------------|----------------
< $100            | Auto-Approve     | 0
$100 - $499.99    | Manager          | 1
$500 - $1,999.99  | Director         | 2
$2,000 - $4,999.99| VP               | 3
>= $5,000         | Finance Committee| 4
Validation Failed | Error Handler    | 5
```
