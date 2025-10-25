# Architecture: Tailwind → Terminal CSS Migration

## System Overview

**Goal**: Replace Tailwind CSS with Terminal CSS while preserving ALL functionality and achieving retro terminal aesthetic.

**Scope**: Single file modification - `tools/livestream/dashboard.html`

**Approach**: 
1. Remove Tailwind CSS CDN and all utility classes
2. Add Terminal CSS CDN
3. Restructure HTML with semantic elements
4. Preserve ALL custom CSS (animations, gradients, effects)
5. Add custom layout CSS (Terminal CSS has no grid system)
6. Override Terminal CSS theme variables for dark terminal aesthetic
7. Keep JavaScript 100% unchanged

## File Structure

```
tools/livestream/dashboard.html (MODIFIED)
├── <head>
│   ├── Terminal CSS CDN (NEW)
│   ├── Chart.js CDN (UNCHANGED)
│   └── <style> Custom CSS (EXPANDED)
│       ├── Terminal CSS variable overrides (NEW)
│       ├── Custom grid layouts (NEW)
│       ├── Phase gradients (PRESERVED)
│       ├── Agent animations (PRESERVED)
│       ├── Progress bars (PRESERVED)
│       ├── Token gauges (PRESERVED)
│       └── Keyframe animations (PRESERVED)
└── <body>
    ├── <header> Page title (NEW semantic structure)
    ├── <section class="session-selector"> (NEW)
    ├── <section class="multi-agent-panel"> (NEW)
    ├── <div class="main-grid"> (NEW custom grid)
    │   ├── <div class="main-content"> (NEW)
    │   │   ├── <section class="phase-indicator">
    │   │   ├── <section class="context-usage">
    │   │   ├── <section class="task-progress">
    │   │   └── <section class="live-logs">
    │   └── <aside class="sidebar"> (NEW)
    │       ├── <section class="session-info">
    │       ├── <section class="statistics">
    │       ├── <section class="connection-status">
    │       └── <nav class="quick-actions">
    ├── <section class="metrics-header"> (NEW)
    ├── <div class="metrics-grid"> (NEW custom grid)
    │   ├── <article class="token-usage">
    │   ├── <article class="test-loop">
    │   ├── <article class="agent-performance">
    │   └── <article class="decision-tracking">
    └── <script> JavaScript (100% UNCHANGED)
```

## Detailed Component Specifications

### 1. HEAD Section

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Context Foundry Livestream</title>
    
    <!-- Terminal CSS CDN (NEW) -->
    <link rel="stylesheet" href="https://unpkg.com/terminal.css@0.7.4/dist/terminal.min.css">
    
    <!-- Chart.js (UNCHANGED) -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    
    <style>
        /* === TERMINAL CSS THEME OVERRIDES === */
        :root {
            --background-color: #0a0a0a;
            --font-color: #e0e0e0;
            --primary-color: #00ff00;
            --secondary-color: #33ff33;
            --invert-font-color: #000000;
            --block-background-color: #111111;
            --global-font-size: 14px;
            --global-line-height: 1.5em;
            --mono-font-stack: 'Monaco', 'Courier New', monospace;
        }
        
        /* === CUSTOM GRID LAYOUTS === */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            margin-top: 1.5rem;
        }
        
        @media (min-width: 1024px) {
            .main-grid {
                grid-template-columns: 2fr 1fr;
            }
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            margin-top: 1.5rem;
        }
        
        @media (min-width: 1024px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        /* === PANEL STYLING === */
        section, article, aside {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        /* === PRESERVED: PHASE GRADIENTS === */
        .phase-scout { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .phase-architect { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .phase-builder { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .phase-complete { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); }
        
        /* === PRESERVED: ANIMATIONS === */
        @keyframes shimmer {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }
        
        @keyframes pulse-red {
            0%, 100% { box-shadow: 0 0 10px rgba(239, 68, 68, 0.4); }
            50% { box-shadow: 0 0 20px rgba(239, 68, 68, 0.6); }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        /* === PRESERVED: PROGRESS BARS === */
        .agent-progress-bar {
            height: 1.5rem;
            background: #1f2937;
            border-radius: 9999px;
            overflow: hidden;
            position: relative;
        }
        
        .agent-progress-fill-active {
            background: linear-gradient(to right, #10b981 0%, #3b82f6 50%, #2563eb 100%);
            background-size: 200% 100%;
            animation: shimmer 3s ease-in-out infinite;
            transition: width 0.5s ease;
            height: 100%;
        }
        
        .agent-progress-fill-idle {
            background: #4b5563;
            transition: width 0.5s ease;
            height: 100%;
        }
        
        .agent-progress-fill-completed {
            background: #10b981;
            transition: width 0.5s ease;
            height: 100%;
        }
        
        /* === PRESERVED: TOKEN GAUGES === */
        .token-gauge {
            background: #1f2937;
            border-radius: 9999px;
            overflow: hidden;
            position: relative;
            height: 1.5rem;
        }
        
        .token-fill {
            height: 100%;
            background: linear-gradient(to right, #10b981 0%, #eab308 50%, #ef4444 100%);
            transition: width 0.5s ease;
        }
        
        .token-critical {
            animation: pulse-red 2s infinite;
        }
        
        .agent-token-safe { background: #10b981; }
        .agent-token-warning { background: #eab308; }
        .agent-token-critical { background: #ef4444; animation: pulse 2s infinite; }
        
        /* === PRESERVED: STATUS INDICATORS === */
        .status-active { color: #10b981; }
        .status-idle { color: #6b7280; }
        .status-spawning { color: #3b82f6; }
        .status-completed { color: #10b981; }
        .status-failed { color: #ef4444; }
        
        /* === PRESERVED: AGENT CARDS === */
        .agent-card {
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            border: 1px solid #374151;
            border-radius: 0.5rem;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }
        
        .agent-card:hover {
            border-color: #4b5563;
            transform: translateX(4px);
        }
        
        /* === PRESERVED: METRIC CARDS === */
        .metric-card {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 0.5rem;
            padding: 1rem;
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            border-color: #374151;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
        }
        
        /* === PRESERVED: DECISION BADGES === */
        .decision-badge {
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: #60a5fa;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            display: inline-block;
        }
        
        .decision-quality-high {
            background: rgba(16, 185, 129, 0.1);
            border-color: rgba(16, 185, 129, 0.3);
            color: #10b981;
        }
        
        .decision-quality-medium {
            background: rgba(234, 179, 8, 0.1);
            border-color: rgba(234, 179, 8, 0.3);
            color: #eab308;
        }
        
        .decision-quality-low {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
            color: #ef4444;
        }
        
        /* === PRESERVED: LOGS === */
        .log-line {
            font-family: 'Monaco', monospace;
            font-size: 12px;
        }
        
        #logs {
            background: #000000;
            padding: 1rem;
            border-radius: 0.5rem;
            height: 24rem;
            overflow-y: auto;
            font-family: 'Monaco', monospace;
            font-size: 12px;
        }
        
        /* === UTILITY CLASSES === */
        .text-green { color: #10b981; }
        .text-yellow { color: #eab308; }
        .text-red { color: #ef4444; }
        .text-blue { color: #3b82f6; }
        .text-gray { color: #6b7280; }
        
        .font-bold { font-weight: bold; }
        .text-sm { font-size: 0.875rem; }
        .text-xs { font-size: 0.75rem; }
        
        .flex { display: flex; }
        .flex-between { justify-content: space-between; }
        .flex-center { align-items: center; }
        .space-y-2 > * + * { margin-top: 0.5rem; }
        .space-y-3 > * + * { margin-top: 0.75rem; }
        
        /* === RESPONSIVE === */
        .main-content > section {
            margin-bottom: 1.5rem;
        }
        
        @media (max-width: 768px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
```

### 2. Body Structure (Semantic HTML)

```html
<body style="padding: 1rem;">
    <!-- Header -->
    <header>
        <h1>🏭 Context Foundry</h1>
        <p style="color: #6b7280;">Real-time monitoring for overnight coding sessions</p>
    </header>

    <!-- Session Selector -->
    <section class="session-selector">
        <label for="sessionSelector" style="display: block; font-weight: bold; margin-bottom: 0.5rem;">Active Session:</label>
        <select id="sessionSelector" style="width: 100%;">
            <option>Loading sessions...</option>
        </select>
    </section>

    <!-- Multi-Agent Panel -->
    <section id="multiAgentPanel" class="multi-agent-panel" style="display: none;">
        <div class="flex flex-between flex-center" style="margin-bottom: 1rem;">
            <h2>🤖 Active Agents</h2>
            <span id="agentCount" class="text-sm text-gray">0 agents</span>
        </div>
        <div id="agentsList" class="space-y-3">
            <div class="text-gray text-sm" style="font-style: italic;">No agents active yet...</div>
        </div>
    </section>

    <!-- Main Grid -->
    <div class="main-grid">
        <!-- Left Column: Main Content -->
        <div class="main-content">
            <!-- Phase Indicator -->
            <section id="phaseCard" class="phase-scout" style="color: white; padding: 1.5rem; border-radius: 0.5rem;">
                <h2 id="phaseName" style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">INITIALIZING</h2>
                <p id="phaseDescription" style="opacity: 0.9; font-size: 0.875rem;">Getting started...</p>
                <div style="margin-top: 1rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.875rem;">
                    <div>
                        <div style="opacity: 0.75;">Iteration</div>
                        <div id="iteration" style="font-size: 1.5rem; font-weight: bold;">0</div>
                    </div>
                    <div>
                        <div style="opacity: 0.75;">Elapsed</div>
                        <div id="elapsed" style="font-size: 1.5rem; font-weight: bold;">0:00</div>
                    </div>
                </div>
            </section>

            <!-- Context Usage -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Context Usage</h3>
                <div style="position: relative; height: 2rem; background: #1f2937; border-radius: 9999px; overflow: hidden;">
                    <div id="contextBar" style="height: 100%; background: linear-gradient(to right, #10b981, #eab308, #ef4444); width: 0%; transition: width 0.5s ease;"></div>
                    <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 0.875rem; font-weight: bold;">
                        <span id="contextPercent">0%</span>
                    </div>
                </div>
                <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #6b7280; text-align: right;">
                    Target: &lt;40% | Warning: &gt;50%
                </div>
            </section>

            <!-- Task Progress -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Task Progress</h3>
                <div style="margin-bottom: 1rem;">
                    <div class="flex flex-between" style="font-size: 0.875rem; margin-bottom: 0.25rem;">
                        <span id="taskCount">0 / 0 tasks</span>
                        <span id="taskPercent">0%</span>
                    </div>
                    <div style="position: relative; height: 0.5rem; background: #1f2937; border-radius: 9999px; overflow: hidden;">
                        <div id="taskBar" style="height: 100%; background: #3b82f6; width: 0%;"></div>
                    </div>
                </div>
                <div class="space-y-2" style="max-height: 16rem; overflow-y: auto;">
                    <div id="taskList" class="text-sm">
                        <div class="text-gray" style="font-style: italic;">No tasks yet...</div>
                    </div>
                </div>
            </section>

            <!-- Live Logs -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Live Logs</h3>
                <div id="logs">
                    <div style="color: #4b5563;">Waiting for logs...</div>
                </div>
            </section>
        </div>

        <!-- Right Column: Sidebar -->
        <aside class="sidebar">
            <!-- Session Info -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Session Info</h3>
                <div class="space-y-3 text-sm">
                    <div>
                        <div class="text-gray">Project</div>
                        <div class="font-bold" id="projectName">-</div>
                    </div>
                    <div>
                        <div class="text-gray">Task</div>
                        <div class="text-xs" id="taskDesc">-</div>
                    </div>
                    <div>
                        <div class="text-gray">Started</div>
                        <div id="startTime">-</div>
                    </div>
                    <div>
                        <div class="text-gray">Estimated Remaining</div>
                        <div id="remaining" class="font-bold text-yellow">-</div>
                    </div>
                </div>
            </section>

            <!-- Statistics -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Statistics</h3>
                <div class="space-y-2 text-sm">
                    <div class="flex flex-between">
                        <span class="text-gray">Iterations</span>
                        <span id="statIterations" class="font-bold">0</span>
                    </div>
                    <div class="flex flex-between">
                        <span class="text-gray">Context Resets</span>
                        <span id="statResets" class="font-bold">0</span>
                    </div>
                    <div class="flex flex-between">
                        <span class="text-gray">Tokens Used</span>
                        <span id="statTokens" class="font-bold">~0</span>
                    </div>
                    <div class="flex flex-between">
                        <span class="text-gray">Est. Cost</span>
                        <span id="statCost" class="font-bold text-green">$0.00</span>
                    </div>
                </div>
            </section>

            <!-- Connection Status -->
            <section>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Connection</h3>
                <div id="connectionStatus" class="flex flex-center">
                    <div style="width: 0.75rem; height: 0.75rem; border-radius: 9999px; background: #6b7280; margin-right: 0.5rem;"></div>
                    <span class="text-sm">Connecting...</span>
                </div>
                <div id="lastUpdate" style="margin-top: 0.5rem; font-size: 0.75rem; color: #6b7280;">Never</div>
            </section>

            <!-- Quick Actions -->
            <nav>
                <h3 style="font-size: 1.125rem; font-weight: bold; margin-bottom: 0.75rem;">Actions</h3>
                <div class="space-y-2">
                    <button onclick="refreshData()" class="btn-primary" style="width: 100%;">
                        🔄 Refresh
                    </button>
                    <button onclick="exportSession()" style="width: 100%;">
                        💾 Export Data
                    </button>
                </div>
            </nav>
        </aside>
    </div>

    <!-- Metrics Header -->
    <section style="margin-top: 1.5rem; border: none; background: transparent; padding: 0;">
        <h2 style="font-size: 1.5rem; font-weight: bold;">📊 Detailed Metrics</h2>
    </section>

    <!-- Metrics Grid -->
    <div class="metrics-grid">
        <!-- Token Usage Panel -->
        <article style="border: 1px solid #1f2937;">
            <h3 class="flex flex-between" style="font-size: 1.125rem; font-weight: bold; color: #e5e7eb; margin-bottom: 1rem;">
                🔢 Token Usage
                <span class="metric-timestamp text-xs text-gray">Not updated</span>
            </h3>
            <div style="margin-bottom: 1rem;">
                <div class="flex flex-between text-sm" style="margin-bottom: 0.5rem;">
                    <span class="text-gray">Used / Budget</span>
                    <span id="tokenCount" class="font-bold" style="color: #e5e7eb;">0 / 200,000</span>
                </div>
                <div id="tokenGauge" class="token-gauge">
                    <div id="tokenFill" class="token-fill" style="width: 0%"></div>
                    <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: bold;">
                        <span id="tokenPercent">0%</span>
                    </div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; font-size: 0.75rem;">
                <div style="text-align: center; padding: 0.5rem; background: #1f2937; border-radius: 0.25rem;">
                    <div class="text-gray">Safe</div>
                    <div class="text-green">< 50%</div>
                </div>
                <div style="text-align: center; padding: 0.5rem; background: #1f2937; border-radius: 0.25rem;">
                    <div class="text-gray">Warning</div>
                    <div class="text-yellow">50-75%</div>
                </div>
                <div style="text-align: center; padding: 0.5rem; background: #1f2937; border-radius: 0.25rem;">
                    <div class="text-gray">Critical</div>
                    <div class="text-red">> 75%</div>
                </div>
            </div>
        </article>

        <!-- Test Loop Analytics -->
        <article style="border: 1px solid #1f2937;">
            <h3 class="flex flex-between" style="font-size: 1.125rem; font-weight: bold; color: #e5e7eb; margin-bottom: 1rem;">
                🧪 Test Loop
                <span class="metric-timestamp text-xs text-gray">Not updated</span>
            </h3>
            <div class="space-y-3">
                <div class="flex flex-between">
                    <span class="text-gray">Iterations</span>
                    <span id="testIterCount" class="font-bold text-blue">0</span>
                </div>
                <div class="flex flex-between">
                    <span class="text-gray">Success Rate</span>
                    <span id="testSuccessRate" class="font-bold text-green">--%</span>
                </div>
                <div id="testIterList" class="space-y-2" style="max-height: 8rem; overflow-y: auto;">
                    <div class="text-gray text-sm" style="font-style: italic;">No test iterations yet</div>
                </div>
            </div>
        </article>

        <!-- Agent Performance -->
        <article style="border: 1px solid #1f2937;">
            <h3 class="flex flex-between" style="font-size: 1.125rem; font-weight: bold; color: #e5e7eb; margin-bottom: 1rem;">
                🤖 Agent Performance
                <span class="metric-timestamp text-xs text-gray">Not updated</span>
            </h3>
            <div id="agentList" class="space-y-2">
                <div class="text-gray text-sm" style="font-style: italic;">No agent data yet</div>
            </div>
        </article>

        <!-- Decision Tracking -->
        <article style="border: 1px solid #1f2937;">
            <h3 class="flex flex-between" style="font-size: 1.125rem; font-weight: bold; color: #e5e7eb; margin-bottom: 1rem;">
                🧠 Decision Quality
                <span class="metric-timestamp text-xs text-gray">Not updated</span>
            </h3>
            <div class="space-y-3">
                <div class="flex flex-between">
                    <span class="text-gray">Total Decisions</span>
                    <span id="decisionCount" class="font-bold text-blue">0</span>
                </div>
                <div class="flex flex-between">
                    <span class="text-gray">Avg Quality</span>
                    <span id="decisionQuality" class="font-bold text-green">--</span>
                </div>
                <div class="flex flex-between">
                    <span class="text-gray">Lessons Applied</span>
                    <span id="decisionLessons" class="font-bold" style="color: #a855f7;">0</span>
                </div>
                <div id="decisionList" class="space-y-2" style="max-height: 8rem; overflow-y: auto; margin-top: 0.75rem;">
                    <div class="text-gray text-sm" style="font-style: italic;">No decisions yet</div>
                </div>
            </div>
        </article>
    </div>

    <!-- JavaScript (100% UNCHANGED) -->
    <script>
        // ALL JAVASCRIPT FROM LINES 413-1051 COPIED VERBATIM
        // NO MODIFICATIONS TO JAVASCRIPT CODE
    </script>
</body>
</html>
```

## Implementation Steps

### Step 1: Backup Original File
```bash
cp tools/livestream/dashboard.html tools/livestream/dashboard.html.tailwind.backup
```

### Step 2: Remove Tailwind CSS
- Delete lines 7-16 (Tailwind CDN and config)
- Remove ALL Tailwind utility classes from HTML elements

### Step 3: Add Terminal CSS
- Add Terminal CSS CDN in `<head>`
- Add Terminal CSS variable overrides in `<style>`

### Step 4: Restructure HTML
- Replace `<div>` with semantic elements (`<section>`, `<article>`, `<aside>`, `<header>`, `<nav>`)
- Add custom classes for layout (.main-grid, .metrics-grid)
- Use inline styles where needed for precise control

### Step 5: Custom CSS
- Preserve ALL existing custom CSS (phases, animations, gauges)
- Add grid layout CSS
- Add utility classes for common patterns

### Step 6: Testing
- Open in browser
- Verify Terminal CSS loaded
- Check all panels render
- Test WebSocket connectivity
- Verify animations work
- Test responsive layout

## Testing Plan

### Manual Visual Testing
1. **Page Load**
   - ✅ Terminal CSS loaded successfully (check Network tab)
   - ✅ No Tailwind references in HTML
   - ✅ Retro terminal aesthetic visible

2. **Layout**
   - ✅ Desktop: 2-column grid (main content + sidebar)
   - ✅ Mobile: Single column layout
   - ✅ All sections visible and properly spaced

3. **Components**
   - ✅ Header displays correctly
   - ✅ Session selector renders
   - ✅ Multi-agent panel shows/hides correctly
   - ✅ Phase indicator with gradient background
   - ✅ Progress bars with gradients
   - ✅ Token gauges with color coding
   - ✅ Logs viewer with monospace font
   - ✅ Metrics panels in grid layout
   - ✅ Buttons styled correctly

4. **Animations**
   - ✅ Shimmer animation on progress bars
   - ✅ Pulse animation on critical warnings
   - ✅ Hover effects on agent cards
   - ✅ Smooth width transitions

### Functional Testing
1. **Session Management**
   - ✅ Session dropdown populates
   - ✅ Changing session reconnects WebSocket

2. **Real-time Updates**
   - ✅ WebSocket connects successfully
   - ✅ Phase updates trigger UI changes
   - ✅ Progress bars update smoothly
   - ✅ Logs append in real-time
   - ✅ Token gauges update

3. **User Interactions**
   - ✅ Refresh button works
   - ✅ Export button downloads JSON
   - ✅ Session selector changes work

4. **Multi-Agent Monitoring**
   - ✅ Agent cards render
   - ✅ Per-agent progress bars animate
   - ✅ Token gauges show correct colors
   - ✅ Status indicators update

### Browser Compatibility
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)

### Responsive Testing
- ✅ Desktop (1920x1080)
- ✅ Tablet (768x1024)
- ✅ Mobile (375x667)

## Success Criteria

### Must Have (Critical)
- ✅ Zero Tailwind CSS references
- ✅ Terminal CSS CDN loaded
- ✅ All functionality preserved
- ✅ WebSocket updates work
- ✅ Gradient progress bars animate
- ✅ Token gauges show colors
- ✅ Responsive layout works
- ✅ No JavaScript errors

### Should Have (Important)
- ✅ Retro terminal aesthetic
- ✅ Semantic HTML structure
- ✅ Clean, readable code
- ✅ Good color contrast
- ✅ Smooth animations

### Nice to Have (Optional)
- ✅ Improved accessibility
- ✅ Better mobile UX
- ✅ Performance improvements

## Rollback Plan

If implementation fails:
```bash
# Restore backup
cp tools/livestream/dashboard.html.tailwind.backup tools/livestream/dashboard.html

# Restart server
# Test original version works
```

## Notes

- JavaScript code is 100% unchanged (lines 413-1051)
- All custom CSS preserved (animations, gradients, effects)
- Terminal CSS provides base styling only
- Custom grid system required (Terminal CSS has none)
- Inline styles used where necessary for precise control
- Semantic HTML improves accessibility and structure
