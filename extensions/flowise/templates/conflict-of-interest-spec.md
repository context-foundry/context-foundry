# Conflict of Interest Detection & Approval Agent - Project Specification

## Project Overview

Build a Flowise Human-in-the-Loop (HIL) workflow for detecting conflicts of interest and routing to human approval before proceeding with engagement decisions. This demonstrates the HIL node pattern with semantic Proceed/Reject outputs.

---

## Workflow Architecture

### Node Count: 5 Total
- 1 Start node
- 1 Condition router (optional - direct connection also valid)
- 1 Conflict Detection agent
- 1 Human Input node (HIL gate)
- 2 Post-approval agents (Approver + Remediator)

### Flow Structure

```
[Start: New Engagement Input]
         ↓
[Agent.ConflictDetector]
         ↓ (populates flow state with conflict data)
[Human Input Node: Conflict Approval Gate]
    ↓ proceed                    ↓ reject
[Agent.ConflictApprover]    [Agent.ConflictRemediator]
```

---

## Agent Specifications

### 1. Agent.ConflictDetector

**Purpose**: Analyze new engagements for potential conflicts of interest

**Capabilities**:
- Check client/company relationships
- Identify project/engagement overlaps
- Assess personnel conflicts of interest
- Calculate risk scores (1-10)
- Populate flow state with conflict details

**System Persona**:
```
<p><em>You are an expert Conflict of Interest Detection agent.</em>
You analyze new client engagements, projects, and team assignments to identify potential conflicts of interest.

Your capabilities:
- Check for existing client relationships that may conflict
- Identify competing interests or confidential information overlaps
- Assess financial conflicts (investments, family relationships)
- Calculate risk scores based on severity
- Recommend mitigations (ethical walls, recusals, disclosure)

When you detect a conflict:
1. Assign a risk score (1-10): 1-3=Low, 4-6=Medium, 7-8=High, 9-10=Critical
2. Summarize the conflict clearly
3. Identify affected parties
4. Suggest mitigations
5. Populate flow state for human review

If NO conflict detected, respond with "No conflicts of interest detected. Engagement may proceed without additional review."
</p>
```

**Tools**: None (uses knowledge base and reasoning)

**Knowledge Base** (Document Store or Vector Embeddings):
- Conflict of interest policies
- Previous conflict cases and resolutions
- Industry-specific conflict rules (legal, consulting, etc.)

**State Management** (Critical - Populates state for HIL node):
```json
"agentUpdateState": [
  {"key": "hitl.pending.action", "value": "Engagement with {{ client_name }}"},
  {"key": "hitl.pending.summary", "value": "{{ conflict_description }}"},
  {"key": "hitl.pending.risk_score", "value": "{{ risk_score }}"},
  {"key": "hitl.pending.cost_estimate", "value": "{{ potential_revenue }}"},
  {"key": "hitl.pending.affected_parties", "value": "{{ affected_parties_list }}"},
  {"key": "hitl.pending.mitigations", "value": "{{ suggested_mitigations }}"}
]
```

**Temperature**: 0.4 (factual analysis)

---

### 2. Human Input Node: Conflict Approval Gate

**Type**: Human-in-the-Loop (HIL) with Proceed/Reject outputs

**Variant**: Fixed Description with Flow State Context

**Configuration**:
```json
{
  "label": "Conflict of Interest Approval",
  "humanInputDescriptionType": "fixed",
  "humanInputDescription": "⚠️ CONFLICT OF INTEREST DETECTED\n\nEngagement: {{ $flow.state.hitl.pending.action }}\n\nConflict Summary:\n{{ $flow.state.hitl.pending.summary }}\n\nRisk Score: {{ $flow.state.hitl.pending.risk_score }}/10\n\nPotential Revenue: ${{ $flow.state.hitl.pending.cost_estimate }}\n\nAffected Parties:\n{{ $flow.state.hitl.pending.affected_parties }}\n\nRecommended Mitigations:\n{{ $flow.state.hitl.pending.mitigations }}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🔵 PROCEED: Approve engagement with conflict waiver\n   • Waiver document will be generated\n   • Affected parties will be notified\n   • Mitigations will be implemented\n\n🔴 REJECT: Decline engagement or escalate to compliance\n   • Engagement will be flagged as declined\n   • Compliance team will be notified\n   • Alternative approaches will be recommended",
  "humanInputEnableFeedback": true
}
```

**Output Anchors**:
- **proceed** (id: `humanInputAgentflow_0-output-proceed`) → Agent.ConflictApprover
- **reject** (id: `humanInputAgentflow_0-output-reject`) → Agent.ConflictRemediator

**Color**: #F06292 (pink - approval workflow theme)

---

### 3. Agent.ConflictApprover

**Purpose**: Handle approved engagements with conflict waivers

**Capabilities**:
- Generate conflict waiver documents
- Send notifications to stakeholders
- Implement recommended mitigations
- Log approval to compliance database
- Document waiver terms

**System Persona**:
```
<p><em>You are an expert Conflict Approval agent.</em>
You handle engagements that have been approved despite identified conflicts of interest.

Your responsibilities:
- Generate conflict waiver documents with clear terms
- Notify affected parties of the conflict and mitigation plan
- Implement ethical walls, information barriers, or recusals as recommended
- Document the approval decision and rationale
- Log the conflict waiver to the compliance database

Always include:
1. Conflict description and risk assessment
2. Approved mitigations and their implementation
3. Monitoring requirements
4. Expiration or review dates for the waiver
5. Responsibilities of each party

Provide clear confirmation of approval and next steps.
</p>
```

**Tools**:
- Document generation tool (for waivers)
- Notification tool (email/Slack)
- Database logging tool

**Temperature**: 0.3 (precise documentation)

---

### 4. Agent.ConflictRemediator

**Purpose**: Handle rejected engagements and escalations

**Capabilities**:
- Document rejection reasoning
- Escalate to compliance team
- Suggest alternative approaches
- Recommend engagement modifications
- Provide compliance guidance

**System Persona**:
```
<p><em>You are an expert Conflict Remediation agent.</em>
You handle engagements that have been rejected due to conflicts of interest.

Your responsibilities:
- Document the rejection decision and human reviewer's feedback
- Escalate high-risk conflicts to the compliance team
- Suggest alternative approaches (e.g., modified scope, different team members, ethical walls)
- Provide guidance on when the conflict might be reconsidered
- Offer compliance resources and policies

If modifications are proposed, you can route back to the Conflict Detector for re-evaluation.

Always provide:
1. Clear explanation of why the engagement was rejected
2. Specific conflict concerns that could not be mitigated
3. Alternative approaches if feasible
4. Timeline for potential reconsideration
5. Resources for the requestor
</p>
```

**Tools**:
- Escalation/notification tool
- Compliance database logging

**Temperature**: 0.4 (helpful guidance)

---

## Flow State Schema

**Required Flow State Structure**:

```json
{
  "hitl": {
    "pending": {
      "action": "string",                    // e.g., "Engagement with Acme Corp"
      "summary": "string",                   // Conflict description
      "risk_score": "number (1-10)",         // Risk assessment
      "cost_estimate": "number",             // Potential revenue or financial impact
      "affected_parties": "string",          // List of affected parties
      "mitigations": "string",               // Recommended mitigations
      "conflict_type": "string",             // e.g., "Client Relationship", "Personnel COI"
      "detection_timestamp": "ISO timestamp" // When conflict was detected
    }
  }
}
```

---

## Edges (Wiring)

### Edge 1: Start → Conflict Detector
```json
{
  "source": "startAgentflow_0",
  "sourceHandle": "startAgentflow_0-output-startAgentflow",
  "target": "agentAgentflow_0",
  "targetHandle": "agentAgentflow_0",
  "type": "agentFlow"
}
```

### Edge 2: Conflict Detector → HIL Node
```json
{
  "source": "agentAgentflow_0",
  "sourceHandle": "agentAgentflow_0-output-agentAgentflow-Agent|AgentExecutor",
  "target": "humanInputAgentflow_0",
  "targetHandle": "humanInputAgentflow_0",
  "type": "agentFlow",
  "data": {
    "sourceColor": "#4DD0E1",
    "targetColor": "#F06292",
    "isHumanInput": false
  }
}
```

### Edge 3: HIL Proceed → Conflict Approver
```json
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-proceed",
  "target": "agentAgentflow_1",
  "targetHandle": "agentAgentflow_1",
  "type": "agentFlow",
  "data": {
    "sourceColor": "#F06292",
    "targetColor": "#4DD0E1",
    "edgeLabel": "Proceed",
    "isHumanInput": true
  }
}
```

### Edge 4: HIL Reject → Conflict Remediator
```json
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-reject",
  "target": "agentAgentflow_2",
  "targetHandle": "agentAgentflow_2",
  "type": "agentFlow",
  "data": {
    "sourceColor": "#F06292",
    "targetColor": "#4DD0E1",
    "edgeLabel": "Reject",
    "isHumanInput": true
  }
}
```

---

## Start Node Configuration

**Input Type**: Form Input

**Form Configuration**:
```json
{
  "startInputType": "formInput",
  "formTitle": "New Engagement Conflict Check",
  "formDescription": "Submit engagement details for conflict of interest screening",
  "formInputTypes": [
    {
      "label": "Client/Company Name",
      "name": "client_name",
      "type": "string",
      "required": true
    },
    {
      "label": "Engagement Type",
      "name": "engagement_type",
      "type": "options",
      "options": ["Consulting", "Legal Services", "Audit", "Advisory", "Other"]
    },
    {
      "label": "Proposed Team Members",
      "name": "team_members",
      "type": "string",
      "description": "Comma-separated list"
    },
    {
      "label": "Engagement Description",
      "name": "engagement_description",
      "type": "string",
      "rows": 4
    },
    {
      "label": "Estimated Revenue",
      "name": "estimated_revenue",
      "type": "number"
    }
  ]
}
```

---

## Pattern Prevention Compliance

**Pattern #1 (Meta-Description)**: ✅ PREVENTED
- Complete workflow JSON with all nodes inline

**Pattern #2 (Missing Agents)**: ✅ PREVENTED
- All 3 agents included in workflow

**Pattern #3 (Separate Config Files)**: ✅ PREVENTED
- Agents are self-contained with inline configurations

**Pattern #4 (Disconnected Nodes)**: ✅ PREVENTED
- All nodes connected: Start → Detector → HIL → Approver/Remediator

**Pattern #5 (Phantom Tools)**: ✅ PREVENTED
- Tools referenced in README/INTEGRATION_GUIDE only
- No tool IDs in JSON that don't exist in Flowise

**Pattern #6-9**: ✅ PREVENTED
- Proper tool structure, complete scenarios, inputParams present, Mermaid diagram included

---

## HIL Node Critical Requirements

✅ **Semantic Output Labels**: "Proceed" and "Reject" (not "Output 0/1")
✅ **Both Paths Wired**: Proceed → Approver, Reject → Remediator
✅ **Flow State Populated**: Detector populates state BEFORE HIL node
✅ **Enable Feedback**: true (capture reviewer notes)
✅ **Color**: #F06292 (pink approval workflow theme)
✅ **Temperature**: 0.0 (if using Dynamic variant)

---

## Success Criteria

### Functional
- ✅ Conflict detection identifies risks accurately
- ✅ HIL node displays conflict details from flow state
- ✅ Proceed path generates waiver and approves engagement
- ✅ Reject path escalates and suggests alternatives
- ✅ Human reviewer can provide feedback
- ✅ Flow state properly tracks conflict data

### Technical
- ✅ Single Flowise workflow JSON file
- ✅ 5 nodes total (Start + 3 agents + 1 HIL)
- ✅ 4 edges connecting all nodes
- ✅ HIL node uses user-provided Proceed/Reject format
- ✅ Zero phantom tool references
- ✅ All pattern preventions applied
- ✅ Mermaid diagram with HIL visualization

### Documentation
- ✅ README with workflow overview and HIL explanation
- ✅ WORKFLOW-DIAGRAM.md with visual flow
- ✅ Integration guide for tools (document generation, notifications)
- ✅ Flow state schema documented
- ✅ Example conflict scenarios

---

## Build Configuration

**Project Name**: conflict-of-interest-agent
**Workflow Complexity**: Medium (3 agents + 1 HIL node)
**Estimated Build Time**: 15-20 minutes
**Test-Driven**: Yes (enable self-healing test loop)
**Pattern Prevention**: Apply all 9 documented Flowise patterns
**Special Focus**: HIL node with user-provided Proceed/Reject structure

---

## BAML Monitoring Focus

Track BAML structured outputs for:

1. **Scout Phase**:
   - Does Scout identify need for HIL node?
   - Does Scout reference the new HIL patterns in library?

2. **Architect Phase**:
   - Does Architect place HIL node between Detector and Approver/Remediator?
   - Does Architect design flow state population strategy?

3. **Builder Phase**:
   - Does Builder use Proceed/Reject output anchor format?
   - Does Builder wire both HIL paths correctly?
   - Does Builder populate HIL description with template variables?

4. **Test Phase**:
   - Do tests validate both proceed and reject paths?
   - Do tests check flow state population?

This will demonstrate if BAML has learned the HIL pattern from the library updates.

---

## Example Conflict Scenarios

### Scenario 1: Client Relationship Conflict (Medium Risk - 6/10)
- **Client**: Acme Corp
- **Conflict**: Existing client's competitor
- **Mitigation**: Ethical wall, separate teams
- **Expected**: Likely approved with waiver

### Scenario 2: Personnel Financial Conflict (High Risk - 8/10)
- **Team Member**: John Doe owns stock in client company
- **Conflict**: Financial interest
- **Mitigation**: Recusal from engagement
- **Expected**: Approved if John recuses, rejected if essential to team

### Scenario 3: Confidential Information Overlap (Critical Risk - 9/10)
- **Conflict**: Team has confidential info from competitor
- **Mitigation**: None feasible
- **Expected**: Rejected, escalate to compliance

---

**Ready for autonomous build with Context Foundry!**
