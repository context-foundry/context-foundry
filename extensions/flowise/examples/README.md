# Vehicle Registration & Parking Management System

A comprehensive multi-agent Flowise AgentFlow v2 workflow for corporate parking management.

## Architecture Overview

This workflow uses the **Routing Pattern** (`afv2-routing-pattern`) to direct user requests to 7 specialized agents based on intent classification.

```
Start Node (Form Intake)
        │
        ▼
  Request Router (ConditionAgent)
        │
        ├──► Vehicle Registration Agent
        ├──► Permit Management Agent
        ├──► Spot Booking Agent
        ├──► Compliance Checking Agent
        ├──► Visitor Permits Agent
        ├──► Reporting Agent
        └──► Violation Management Agent
```

## Agents

### 1. Vehicle Registration Agent
**Color:** Blue (#60a5fa)

Handles:
- License plate format validation by state
- VIN capture and NHTSA decoding
- Insurance document management (upload, expiration tracking)
- Employee/contractor verification via Workday

**Tools:**
- `workdayEmployeeAPI` - Employee data lookup
- `vehicleDatabaseAPI` - Vehicle registration storage
- `nhtsaVinDecoder` - VIN validation
- `calculator` - Date calculations

### 2. Permit Management Agent
**Color:** Purple (#a78bfa)

Handles:
- Eligibility validation based on employee status
- Multi-level approval workflows (Manager → Facilities → Security)
- Waitlist automation with priority queuing
- Permit renewal notifications

**Tools:**
- `workdayEmployeeAPI` - Employee eligibility
- `permitDatabaseAPI` - Permit CRUD operations
- `approvalWorkflowAPI` - Multi-level approvals
- `notificationService` - Email/SMS alerts
- `calculator` - Priority scoring

### 3. Spot Booking Agent
**Color:** Green (#34d399)

Handles:
- Daily parking reservations
- Real-time availability checking
- Double-booking prevention
- Preferred spot assignment by permit type
- Cancellation/modification management

**Tools:**
- `spotAvailabilityAPI` - Real-time availability
- `bookingManagementAPI` - Reservation CRUD
- `calendarIntegrationAPI` - Schedule sync
- `notificationService` - Confirmations
- `calculator` - Availability calculations
- `currentDateTime` - Booking validation

### 4. Compliance Checking Agent
**Color:** Red (#f87171)

Handles:
- Automated daily scans for expired insurance
- Violation detection and flagging
- Suspension triggers for non-compliance
- Notification workflows for compliance issues

**Tools:**
- `complianceScanAPI` - Batch compliance scans
- `insuranceVerificationAPI` - Insurance validation
- `workdayEmployeeAPI` - Employment status
- `violationTrackingAPI` - Violation records
- `notificationService` - Compliance alerts
- `calculator` - Expiration calculations
- `currentDateTime` - Scan timestamps

### 5. Visitor Permits Agent
**Color:** Yellow (#fbbf24)

Handles:
- Temporary permit generation (1-5 days)
- QR code generation for gate access
- Host employee validation
- Pre-registration workflows

**Tools:**
- `visitorPermitAPI` - Visitor permit management
- `qrCodeGeneratorAPI` - QR code creation
- `hostValidationAPI` - Host privilege check
- `notificationService` - Visitor notifications
- `currentDateTime` - Validity windows

### 6. Reporting Agent
**Color:** Cyan (#06b6d4)

Handles:
- Occupancy analytics and dashboards
- Revenue tracking and forecasting
- Violation statistics and trends
- Waitlist analytics and projections

**Tools:**
- `analyticsDataAPI` - Usage metrics
- `reportGeneratorAPI` - PDF/chart generation
- `financialDataAPI` - Revenue data
- `calculator` - Statistical calculations
- `currentDateTime` - Report timestamps

### 7. Violation Management Agent
**Color:** Pink (#f472b6)

Handles:
- Admin tools for enforcement actions
- Violation dispute resolution workflow
- Fine calculation and tracking
- Appeals process management

**Tools:**
- `violationManagementAPI` - Violation CRUD
- `fineCalculatorAPI` - Fine calculation matrix
- `paymentTrackingAPI` - Payment status
- `appealsWorkflowAPI` - Appeals process
- `notificationService` - Violation notices
- `calculator` - Fine calculations
- `currentDateTime` - Deadlines

## Installation

### Prerequisites
- Flowise v2.0.0 or higher
- API credentials for:
  - Anthropic API (Claude Sonnet 4.5)
  - Workday API (employee data)
  - Internal Parking API endpoints

### Import Steps

1. Open Flowise and navigate to **Agentflows**
2. Click **Add New** or the **+** button
3. Click the menu icon (three dots) and select **Load Chatflow**
4. Select `vehicle-parking-flow.json`
5. Configure credentials in each node

### Credential Configuration

Each agent requires the following credentials to be configured:

1. **Anthropic API Key** - For Claude Sonnet 4.5 model
2. **Internal API Token** - `{{apiToken}}` for parking system APIs
3. **Workday Token** - `{{workdayToken}}` for employee lookups
4. **Calendar Token** - `{{calendarToken}}` for calendar integration
5. **Finance Token** - `{{financeToken}}` for financial data
6. **Insurance Token** - `{{insuranceToken}}` for insurance verification

## API Endpoints Configuration

The workflow expects the following API endpoints. Update the `apiBase` URLs in each tool to match your infrastructure:

### Internal Parking APIs
- `https://api.parking.internal/vehicles` - Vehicle database
- `https://api.parking.internal/permits` - Permit management
- `https://api.parking.internal/bookings` - Spot reservations
- `https://api.parking.internal/compliance/scan` - Compliance scans
- `https://api.parking.internal/violations` - Violation records
- `https://api.parking.internal/visitor-permits` - Visitor permits
- `https://api.parking.internal/qr-generate` - QR code generation
- `https://api.parking.internal/analytics/query` - Analytics data
- `https://api.parking.internal/reports/generate` - Report generation
- `https://api.parking.internal/notifications` - Email/SMS service
- `https://api.parking.internal/approvals` - Approval workflows
- `https://api.parking.internal/appeals` - Appeals process
- `https://api.parking.internal/payments` - Payment tracking
- `https://api.parking.internal/fines/calculate` - Fine calculator
- `https://api.parking.internal/availability` - Spot availability

### External APIs
- `https://api.workday.com/v1/employees/` - Workday employee data
- `https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/` - NHTSA VIN decoder
- `https://api.insurance.external/verify` - Insurance verification
- `https://api.calendar.internal/events` - Calendar integration
- `https://api.finance.internal/parking` - Financial data

## Usage

### Form Inputs

When the workflow starts, users complete a form with:

| Field | Type | Description |
|-------|------|-------------|
| Request Type | Dropdown | Selects target agent |
| Employee ID | Text | User's employee identifier |
| Request Details | Text | Detailed description of request |
| License Plate | Text | Vehicle plate number (optional) |
| VIN | Text | Vehicle identification number (optional) |
| Date | Text | Relevant date for request (optional) |

### Example Requests

**Vehicle Registration:**
```
Request Type: Vehicle Registration
Employee ID: EMP12345
Request Details: Register my new vehicle - 2024 Tesla Model Y
License Plate: ABC1234
VIN: 5YJYGDEE4MF123456
```

**Permit Management:**
```
Request Type: Permit Management
Employee ID: EMP12345
Request Details: Apply for standard parking permit at HQ building
```

**Spot Booking:**
```
Request Type: Spot Booking
Employee ID: EMP12345
Request Details: Book parking spot for tomorrow
Date: 2024-01-15
```

**Visitor Permit:**
```
Request Type: Visitor Permit
Employee ID: EMP12345
Request Details: Request visitor permit for client meeting
Date: 2024-01-20
```

## State Management

Each agent updates the workflow state with its results:

```javascript
{
  "vehicleRegistrationResult": "...",
  "permitManagementResult": "...",
  "spotBookingResult": "...",
  "complianceCheckResult": "...",
  "visitorPermitResult": "...",
  "reportingResult": "...",
  "violationManagementResult": "...",

  // Status flags
  "registrationStatus": "completed",
  "permitStatus": "completed",
  "bookingStatus": "completed",
  "complianceStatus": "completed",
  "visitorStatus": "completed",
  "reportStatus": "completed",
  "violationStatus": "completed"
}
```

## Customization

### Adding New Request Types

1. Add new scenario to `conditionAgentAgentflow_0.inputs.conditionAgentScenarios`
2. Create new agent node with unique ID
3. Add edge from router to new agent
4. Update router's `outputAnchors` with new output

### Modifying Agent Behavior

Each agent's `agentMessages[0].content` contains the system prompt. Modify this to:
- Change business rules
- Update fine amounts
- Adjust approval workflows
- Add new validation logic

### Adding Tools

Add to agent's `agentTools` array:

```json
{
  "agentSelectedTool": "customHttpTool",
  "toolName": "newToolName",
  "toolDescription": "What this tool does",
  "toolMethod": "POST",
  "apiBase": "https://api.example.com/endpoint",
  "headers": { "Authorization": "Bearer {{token}}" },
  "agentSelectedToolRequiresHumanInput": ""
}
```

## Testing

### Validation Checklist

- [ ] Start node has `formTitle`, `formDescription`, `formInputTypes`
- [ ] Router has 7 scenarios matching 7 agents
- [ ] Each scenario has `scenario`, `condition`, `model`, `instructions`, `input`
- [ ] All agents have complete `inputParams` (15 fields)
- [ ] All edges connect router outputs to agent inputs
- [ ] Tools use correct field names (`apiBase` not `baseUrl`)
- [ ] Variables use `{{variableName}}` syntax

### Test Cases

1. **Happy Path:** Submit each request type and verify correct routing
2. **Validation:** Submit invalid employee ID, check error handling
3. **State Updates:** Verify state variables populated after agent completion
4. **Tool Execution:** Confirm API calls execute with correct parameters

## Troubleshooting

### Common Issues

**Router not routing correctly:**
- Check `conditionAgentScenarios` array structure
- Verify variable syntax: `{{$flow.startOutput}}`
- Ensure model temperature is low (0.1-0.3)

**Agent not editable in UI:**
- Verify `inputParams` array has 15+ fields
- Check all required fields present

**Tools not executing:**
- Confirm credentials configured in Flowise
- Check `apiBase` URLs are correct
- Verify `agentSelectedToolRequiresHumanInput` is empty string

**Workflow won't import:**
- Validate JSON syntax
- Check all node IDs are unique
- Verify edges reference valid node IDs

## Architecture Patterns Used

This workflow follows the Flowise expertise patterns from:
`/extensions/flowise/patterns/flowise-expertise.json`

**Primary Pattern:** `afv2-routing-pattern`
- Intent-based routing using ConditionAgent
- Number of scenarios equals number of downstream agents
- Low temperature (0.1) for deterministic routing

**Anti-Patterns Avoided:**
- No separate configuration files (single JSON)
- No meta-descriptions (actual implementation)
- Complete inputParams arrays on all agents
- Proper variable syntax throughout

## License

Internal use only. For corporate parking management systems.

## Support

Contact the Facilities or IT department for assistance with:
- API endpoint configuration
- Credential setup
- Custom modifications
