# Workday Extend: Platform Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0875e1', 'primaryTextColor': '#fff', 'primaryBorderColor': '#0056b3', 'secondaryColor': '#f0f4f8', 'lineColor': '#576574', 'fontFamily': 'Inter, sans-serif', 'fontSize': '13px'}}}%%

flowchart TB
    subgraph TENANT["Workday Tenant"]
        direction TB

        subgraph UI["Presentation Layer"]
            direction LR
            PMD["<b>PMD</b><br/>Pages · Forms · Lists<br/>Dashboards · Canvas Components"]
            CANVAS["<b>Canvas Kit</b><br/>React Components<br/>Apache 2.0 OSS"]
        end

        subgraph APP["Application Layer"]
            direction LR
            AMD["<b>AMD</b><br/>App Manifest · Version<br/>Dependencies · Navigation"]
            APPBUILDER["<b>App Builder</b><br/>Visual + Code Mode<br/>JSON editing"]
        end

        subgraph SVC["Service Layer"]
            direction LR
            SMD["<b>SMD</b><br/>Business Objects · Fields<br/>Business Processes · REST"]
            ORCH["<b>Orchestrations</b><br/>Sequential · Parallel<br/>Conditional · Sub-Orch"]
        end

        subgraph SEC["Security & Data"]
            direction LR
            SECURITY["<b>Security Model</b><br/>Domains · DSPs · BPSPs<br/>Security Groups"]
            DATA["<b>Data Layer</b><br/>Object Store<br/>Core + Custom BOs · WQL"]
        end
    end

    subgraph EXT["External Ecosystem"]
        direction LR
        REST["<b>REST API</b><br/>OAuth 2.0 · JSON"]
        SOAP["<b>SOAP / WWS</b><br/>XML · Payroll"]
        GRAPH["<b>Graph API</b><br/>Data Relationships"]
        RAAS["<b>RaaS</b><br/>Report Endpoints"]
    end

    subgraph TOOLS["Developer Tools"]
        direction LR
        PORTAL["<b>Developer Portal</b><br/>developer.workday.com"]
        COPILOT["<b>Developer Copilot</b><br/>AI Code Gen"]
        CLI["<b>Developer CLI</b><br/>DevOps"]
    end

    PMD --> AMD
    SMD --> AMD
    AMD --> SEC
    ORCH --> SMD
    CANVAS -.-> PMD
    DATA --> SMD
    SVC --> EXT
    TOOLS --> APP

    style TENANT fill:#f0f4f8,stroke:#0875e1,stroke-width:3px,color:#1a1a2e
    style UI fill:#e3f2fd,stroke:#0875e1,stroke-width:2px,color:#1a1a2e
    style APP fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#1a1a2e
    style SVC fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1a1a2e
    style SEC fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#1a1a2e
    style EXT fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#1a1a2e
    style TOOLS fill:#e0f7fa,stroke:#00838f,stroke-width:2px,color:#1a1a2e
    style PMD fill:#1565c0,stroke:#0d47a1,color:#fff
    style CANVAS fill:#42a5f5,stroke:#1565c0,color:#fff
    style AMD fill:#ef6c00,stroke:#e65100,color:#fff
    style APPBUILDER fill:#ff9800,stroke:#ef6c00,color:#fff
    style SMD fill:#2e7d32,stroke:#1b5e20,color:#fff
    style ORCH fill:#66bb6a,stroke:#2e7d32,color:#fff
    style SECURITY fill:#c62828,stroke:#b71c1c,color:#fff
    style DATA fill:#ef5350,stroke:#c62828,color:#fff
    style REST fill:#7b1fa2,stroke:#6a1b9a,color:#fff
    style SOAP fill:#9c27b0,stroke:#7b1fa2,color:#fff
    style GRAPH fill:#ab47bc,stroke:#9c27b0,color:#fff
    style RAAS fill:#ce93d8,stroke:#ab47bc,color:#1a1a2e
    style PORTAL fill:#00838f,stroke:#006064,color:#fff
    style COPILOT fill:#00acc1,stroke:#00838f,color:#fff
    style CLI fill:#4dd0e1,stroke:#00acc1,color:#1a1a2e
```

## Reading Guide

- **Blue (top)**: Presentation layer -- PMD defines pages/forms, Canvas Kit provides the React component library
- **Orange (middle-top)**: Application layer -- AMD is the manifest that ties PMD and SMD together
- **Green (middle)**: Service layer -- SMD defines business objects and processes; Orchestrations handle workflows
- **Red (bottom)**: Security & Data -- Security domains/policies control all access; Data Layer holds business objects
- **Purple (external)**: Four API types for external connectivity (REST, SOAP, Graph, RaaS)
- **Teal (tools)**: Developer Portal, Copilot, and CLI feed into the application layer
