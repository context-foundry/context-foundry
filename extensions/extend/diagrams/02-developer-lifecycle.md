# Workday Extend: Developer Lifecycle

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0875e1', 'primaryTextColor': '#fff', 'lineColor': '#576574', 'fontFamily': 'Inter, sans-serif', 'fontSize': '13px'}}}%%

flowchart LR
    subgraph SETUP["1. Setup"]
        direction TB
        S1["Register at<br/><b>developer.workday.com</b>"]
        S2["Accept License<br/>Agreement"]
        S3["Provision Developer<br/>Tenant · 1-5 days"]
        S4["Create API Client<br/>OAuth 2.0 credentials"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph BUILD["2. Build"]
        direction TB
        B1["App Builder<br/>Browser-based IDE"]
        B2["Define Business<br/>Objects — SMD"]
        B3["Design Pages<br/>& Forms — PMD"]
        B4["Configure Security<br/>Domains & Policies"]
        B5["Build Orchestrations<br/>Workflow automation"]
        B1 --> B2 --> B3 --> B4 --> B5
    end

    subgraph TEST["3. Test"]
        direction TB
        T1["App Preview<br/>Real-time in builder"]
        T2["Sandbox Tenant<br/>Full regression"]
        T3["Manual Test Cases<br/>No automated framework"]
        T4["Security Validation<br/>Test all roles"]
        T1 --> T2 --> T3 --> T4
    end

    subgraph DEPLOY["4. Deploy"]
        direction TB
        D1["Create Migration Set"]
        D2["Set Migration IDs<br/>Never change after deploy"]
        D3["Deploy to IMPL<br/>Quick Deploy available"]
        D4["Re-enter Credentials<br/>Creds do not migrate"]
        D5["Activate Security<br/>Policies"]
        D1 --> D2 --> D3 --> D4 --> D5
    end

    subgraph MAINT["5. Maintain"]
        direction TB
        M1["Monitor in<br/>App Manager"]
        M2["Test Before<br/>R1 / R2 Releases"]
        M3["Version Updates<br/>Semantic versioning"]
        M1 --> M2 --> M3
    end

    SETUP --> BUILD --> TEST --> DEPLOY --> MAINT

    style SETUP fill:#e3f2fd,stroke:#0875e1,stroke-width:2px,color:#1a1a2e
    style BUILD fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1a1a2e
    style TEST fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#1a1a2e
    style DEPLOY fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#1a1a2e
    style MAINT fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#1a1a2e

    style S1 fill:#1565c0,stroke:#0d47a1,color:#fff
    style S2 fill:#1976d2,stroke:#1565c0,color:#fff
    style S3 fill:#1e88e5,stroke:#1976d2,color:#fff
    style S4 fill:#42a5f5,stroke:#1e88e5,color:#fff

    style B1 fill:#2e7d32,stroke:#1b5e20,color:#fff
    style B2 fill:#388e3c,stroke:#2e7d32,color:#fff
    style B3 fill:#43a047,stroke:#388e3c,color:#fff
    style B4 fill:#4caf50,stroke:#43a047,color:#fff
    style B5 fill:#66bb6a,stroke:#4caf50,color:#fff

    style T1 fill:#e65100,stroke:#bf360c,color:#fff
    style T2 fill:#ef6c00,stroke:#e65100,color:#fff
    style T3 fill:#f57c00,stroke:#ef6c00,color:#fff
    style T4 fill:#fb8c00,stroke:#f57c00,color:#fff

    style D1 fill:#c62828,stroke:#b71c1c,color:#fff
    style D2 fill:#d32f2f,stroke:#c62828,color:#fff
    style D3 fill:#e53935,stroke:#d32f2f,color:#fff
    style D4 fill:#ef5350,stroke:#e53935,color:#fff
    style D5 fill:#f44336,stroke:#ef5350,color:#fff

    style M1 fill:#6a1b9a,stroke:#4a148c,color:#fff
    style M2 fill:#7b1fa2,stroke:#6a1b9a,color:#fff
    style M3 fill:#9c27b0,stroke:#7b1fa2,color:#fff
```

## Key Gotchas by Phase

| Phase | Critical Warning |
|-------|-----------------|
| Setup | Tenant provisioning takes 1-5 business days |
| Build | Everything is metadata-driven — no arbitrary code execution |
| Test | No automated testing framework exists; all testing is manual |
| Deploy | Credentials never migrate; Migration IDs must never change |
| Maintain | Test before every biannual Workday release (R1 March, R2 September) |
