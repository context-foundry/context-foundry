# Workday Extend: Orchestrations & Integrations

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0875e1', 'primaryTextColor': '#fff', 'lineColor': '#576574', 'fontFamily': 'Inter, sans-serif', 'fontSize': '13px'}}}%%

flowchart TB
    subgraph TRIGGERS["Triggers"]
        direction LR
        EVT["Event-Driven<br/>BP completion<br/>Data change"]
        SCHED["Scheduled<br/>Cron-based<br/>Recurring"]
        MANUAL["Manual<br/>User-initiated<br/>Task action"]
        API_T["API Call<br/>External request<br/>Webhook callback"]
    end

    subgraph ORCH_ENGINE["Orchestration Engine"]
        direction TB

        subgraph PATTERNS["Execution Patterns"]
            direction LR
            SEQ["<b>Sequential</b><br/>Step by step"]
            PAR["<b>Parallel</b><br/>Concurrent branches"]
            COND["<b>Conditional</b><br/>If/else routing"]
            LOOP["<b>Loop</b><br/>Iterate collections"]
        end

        subgraph STEPS["Step Types"]
            direction LR
            WQL_S["WQL Query<br/>Read Workday data"]
            REST_S["REST Call<br/>Internal or external"]
            SOAP_S["SOAP Call<br/>WWS operations"]
            XFORM["Transform<br/>Data mapping"]
            NOTIFY["Notification<br/>Email, in-app"]
            SUB["Sub-Orchestration<br/>Reusable modules"]
        end

        ERR["<b>Error Handling</b><br/>Retry · Compensate · Alert"]
    end

    subgraph INTEGRATIONS["Integration Targets"]
        direction LR

        subgraph WD_INT["Workday Internal"]
            direction TB
            CORE_API["Core REST API<br/>/ccx/api/v1/"]
            WWS["SOAP / WWS<br/>Payroll, Finance"]
            RAAS_I["RaaS<br/>Report endpoints"]
            GRAPH_I["Graph API<br/>Data relationships"]
        end

        subgraph EXT_INT["External Systems"]
            direction TB
            EXT_REST["External REST<br/>SaaS, custom APIs"]
            SFTP["SFTP / File<br/>Batch transfers"]
            MIDDLEWARE["Middleware<br/>MuleSoft, Boomi"]
        end
    end

    subgraph BP["Business Processes"]
        direction LR
        INIT["Initiate"]
        APPROVE["Approval<br/>Chain"]
        REVIEW["Review<br/>Steps"]
        COMPLETE["Complete<br/>& Notify"]
        INIT --> APPROVE --> REVIEW --> COMPLETE
    end

    TRIGGERS --> ORCH_ENGINE
    PATTERNS --> STEPS
    STEPS --> ERR
    ORCH_ENGINE --> INTEGRATIONS
    ORCH_ENGINE --> BP

    style TRIGGERS fill:#e3f2fd,stroke:#0875e1,stroke-width:2px,color:#1a1a2e
    style ORCH_ENGINE fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px,color:#1a1a2e
    style PATTERNS fill:#c8e6c9,stroke:#43a047,stroke-width:1px,color:#1a1a2e
    style STEPS fill:#a5d6a7,stroke:#66bb6a,stroke-width:1px,color:#1a1a2e
    style INTEGRATIONS fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#1a1a2e
    style WD_INT fill:#e1bee7,stroke:#9c27b0,stroke-width:1px,color:#1a1a2e
    style EXT_INT fill:#ce93d8,stroke:#ab47bc,stroke-width:1px,color:#1a1a2e
    style BP fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#1a1a2e

    style EVT fill:#1565c0,stroke:#0d47a1,color:#fff
    style SCHED fill:#1976d2,stroke:#1565c0,color:#fff
    style MANUAL fill:#1e88e5,stroke:#1976d2,color:#fff
    style API_T fill:#42a5f5,stroke:#1e88e5,color:#fff

    style SEQ fill:#2e7d32,stroke:#1b5e20,color:#fff
    style PAR fill:#388e3c,stroke:#2e7d32,color:#fff
    style COND fill:#43a047,stroke:#388e3c,color:#fff
    style LOOP fill:#66bb6a,stroke:#43a047,color:#fff

    style WQL_S fill:#4caf50,stroke:#388e3c,color:#fff
    style REST_S fill:#66bb6a,stroke:#4caf50,color:#fff
    style SOAP_S fill:#81c784,stroke:#66bb6a,color:#1a1a2e
    style XFORM fill:#a5d6a7,stroke:#81c784,color:#1a1a2e
    style NOTIFY fill:#c8e6c9,stroke:#a5d6a7,color:#1a1a2e
    style SUB fill:#e8f5e9,stroke:#c8e6c9,color:#1a1a2e
    style ERR fill:#c62828,stroke:#b71c1c,color:#fff

    style CORE_API fill:#7b1fa2,stroke:#6a1b9a,color:#fff
    style WWS fill:#8e24aa,stroke:#7b1fa2,color:#fff
    style RAAS_I fill:#9c27b0,stroke:#8e24aa,color:#fff
    style GRAPH_I fill:#ab47bc,stroke:#9c27b0,color:#fff
    style EXT_REST fill:#6a1b9a,stroke:#4a148c,color:#fff
    style SFTP fill:#7b1fa2,stroke:#6a1b9a,color:#fff
    style MIDDLEWARE fill:#8e24aa,stroke:#7b1fa2,color:#fff

    style INIT fill:#e65100,stroke:#bf360c,color:#fff
    style APPROVE fill:#ef6c00,stroke:#e65100,color:#fff
    style REVIEW fill:#f57c00,stroke:#ef6c00,color:#fff
    style COMPLETE fill:#ff9800,stroke:#f57c00,color:#fff
```

## Key Concepts

- **Triggers**: Events, schedules, manual actions, or API calls initiate orchestrations
- **Patterns**: Sequential, parallel, conditional, and loop execution models
- **Steps**: WQL queries, REST/SOAP calls, transforms, notifications, and sub-orchestrations
- **Error Handling**: Retry policies, compensation logic, and alert routing
- **Integration Targets**: Both Workday internal APIs and external systems
- **Business Processes**: Orchestrations can initiate and participate in approval workflows
