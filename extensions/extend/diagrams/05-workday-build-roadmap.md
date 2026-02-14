# Workday Build Platform: Roadmap Status (Feb 2026)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0875e1', 'primaryTextColor': '#fff', 'lineColor': '#576574', 'fontFamily': 'Inter, sans-serif', 'fontSize': '13px'}}}%%

flowchart TB
    TITLE["<b>Workday Build Platform</b><br/>Status as of February 2026"]

    subgraph GA_2024["GA — 2024"]
        direction LR
        VISUAL["Visual UI Mode<br/>App Builder"]
        DARKMODE["Dark Mode<br/>App & Orch Builder"]
        BIDI["Bidirectional BO<br/>Relationships"]
        QUICKDEPLOY["Quick Deploy<br/>to IMPL"]
        COPILOT_V1["Copilot v1<br/>2024 R2"]
        BOW["Built on Workday<br/>Partner Apps"]
    end

    subgraph TARGETED_2025["Targeted GA end 2025 — Unconfirmed"]
        direction LR
        COPILOT_V2["Developer<br/>Copilot v2"]
        DEVCLI["Developer<br/>CLI"]
        AIWIDGETS["AI<br/>Widgets"]
        AISERVICES["AI<br/>Services"]
    end

    subgraph EA_2025["Early Adopter — end 2025"]
        direction LR
        GATEWAY["Agent Gateway<br/>MCP + A2A compliant"]
    end

    subgraph H1_2026["Targeted H1 2026 — On Track"]
        direction LR
        FLOWISE["Flowise<br/>Agent Builder<br/>Extend Professional"]
        DATACLOUD_EA["Data Cloud<br/>Early Adopter"]
    end

    subgraph LATER_2026["GA later 2026"]
        direction LR
        DATACLOUD_GA["Data Cloud<br/>General Availability"]
    end

    subgraph PARTNERS["Agent Partner Network — 15+ Partners"]
        direction LR
        P1["Accenture"]
        P2["AWS"]
        P3["Google Cloud"]
        P4["Microsoft"]
        P5["IBM"]
        P6["Adobe"]
    end

    subgraph ACQUISITIONS["Key Acquisitions 2025"]
        direction LR
        ACQ1["<b>Flowise</b><br/>Aug 2025<br/>AI Agent Builder<br/>46K GitHub stars"]
        ACQ2["<b>Pipedream</b><br/>Nov 2025<br/>3,000+ connectors"]
        ACQ3["<b>Sana</b><br/>2025 · $1.1B<br/>AI Interface Layer"]
    end

    TITLE --> GA_2024
    TITLE --> TARGETED_2025
    TITLE --> EA_2025
    TITLE --> H1_2026
    H1_2026 --> LATER_2026
    GATEWAY --> PARTNERS
    ACQUISITIONS -.-> H1_2026

    style TITLE fill:#0d47a1,stroke:#0a3d91,stroke-width:3px,color:#fff

    style GA_2024 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1a1a2e
    style VISUAL fill:#2e7d32,stroke:#1b5e20,color:#fff
    style DARKMODE fill:#388e3c,stroke:#2e7d32,color:#fff
    style BIDI fill:#43a047,stroke:#388e3c,color:#fff
    style QUICKDEPLOY fill:#4caf50,stroke:#43a047,color:#fff
    style COPILOT_V1 fill:#66bb6a,stroke:#4caf50,color:#fff
    style BOW fill:#81c784,stroke:#66bb6a,color:#1a1a2e

    style TARGETED_2025 fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#1a1a2e
    style COPILOT_V2 fill:#ef6c00,stroke:#e65100,color:#fff
    style DEVCLI fill:#f57c00,stroke:#ef6c00,color:#fff
    style AIWIDGETS fill:#fb8c00,stroke:#f57c00,color:#fff
    style AISERVICES fill:#ff9800,stroke:#fb8c00,color:#fff

    style EA_2025 fill:#e3f2fd,stroke:#0875e1,stroke-width:2px,color:#1a1a2e
    style GATEWAY fill:#0875e1,stroke:#0056b3,color:#fff

    style H1_2026 fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#1a1a2e
    style FLOWISE fill:#c62828,stroke:#b71c1c,color:#fff
    style DATACLOUD_EA fill:#d32f2f,stroke:#c62828,color:#fff

    style LATER_2026 fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#1a1a2e
    style DATACLOUD_GA fill:#6a1b9a,stroke:#4a148c,color:#fff

    style PARTNERS fill:#e0f7fa,stroke:#00838f,stroke-width:2px,color:#1a1a2e
    style P1 fill:#00838f,stroke:#006064,color:#fff
    style P2 fill:#0097a7,stroke:#00838f,color:#fff
    style P3 fill:#00acc1,stroke:#0097a7,color:#fff
    style P4 fill:#00bcd4,stroke:#00acc1,color:#fff
    style P5 fill:#26c6da,stroke:#00bcd4,color:#fff
    style P6 fill:#4dd0e1,stroke:#26c6da,color:#1a1a2e

    style ACQUISITIONS fill:#fafafa,stroke:#9e9e9e,stroke-width:2px,color:#1a1a2e
    style ACQ1 fill:#c62828,stroke:#b71c1c,color:#fff
    style ACQ2 fill:#6a1b9a,stroke:#4a148c,color:#fff
    style ACQ3 fill:#0d47a1,stroke:#0a3d91,color:#fff
```

## Status Legend

| Color | Meaning |
|-------|---------|
| Green | GA — shipped and available |
| Amber | Targeted GA end 2025 — not yet explicitly confirmed |
| Blue | Early Adopter — limited availability |
| Red | Targeted H1 2026 — on track but unconfirmed |
| Purple | Planned GA later 2026 |
| Teal | Partner ecosystem |
| Gray | Strategic acquisitions feeding the platform |

*Roadmap items should be re-verified against developer.workday.com before relying on them.*
