# Codebase Analysis Report

## Project Overview
- **Type**: Python web application (livestream monitoring dashboard)
- **Languages**: Python (backend), HTML/JavaScript (frontend)
- **Architecture**: WebSocket-based real-time monitoring dashboard for Context Foundry autonomous builds

## Key Files
- **Entry point**: tools/livestream/server.py
- **Frontend**: tools/livestream/dashboard.html (TARGET FILE FOR REDESIGN)
- **Config**: tools/livestream/config.py
- **Tests**: tools/livestream/tests/

## Current Dashboard Architecture

### HTML Structure (dashboard.html)
- **Size**: 1,053 lines
- **CSS Framework**: Tailwind CSS (via CDN)
  - CDN link: https://cdn.tailwindcss.com?plugins=forms,typography,aspect-ratio
  - Uses utility classes extensively (bg-gray-900, p-6, rounded-lg, etc.)
- **Custom CSS**: Extensive custom styling (lines 19-149)
  - Phase indicator gradients (.phase-scout, .phase-architect, .phase-builder, .phase-complete)
  - Metric cards with hover effects
  - Token gauges with gradient fills
  - Agent cards with animations
  - Multi-agent progress bars with shimmer animations
  - Keyframe animations (shimmer, pulse-red, pulse)

### Key Features (MUST PRESERVE)
1. **Multi-Agent Monitoring Panel** (lines 166-175)
   - Shows active agents with status indicators
   - Horizontal gradient progress bars per agent
   - Per-agent token usage gauges with color warnings
   - Real-time updates via WebSocket

2. **Phase Indicator** (lines 182-195)
   - Dynamic gradient backgrounds based on phase
   - Iteration counter and elapsed time

3. **Context Usage Bar** (lines 198-209)
   - Gradient progress bar (green → yellow → red)
   - Percentage overlay

4. **Session Selector** (lines 159-164)
   - Dropdown for multiple sessions

5. **Live Logs Viewer** (lines 233-238)
   - Monospace font, auto-scroll
   - Syntax highlighting for emojis

6. **Statistics & Metrics** (lines 315-411)
   - Token usage panel with gauge
   - Test loop analytics
   - Agent performance tracking
   - Decision quality tracking

7. **WebSocket Integration** (lines 754-832)
   - Real-time updates
   - Auto-reconnect logic
   - Phase update handling

## Code to Modify

### Task: Replace Tailwind CSS with Terminal CSS

**Files to change**:
- `tools/livestream/dashboard.html` (complete redesign)

**Approach**:
1. **Remove Tailwind**:
   - Delete Tailwind CDN script tag (line 8)
   - Delete Tailwind config (lines 9-16)
   - Remove ALL utility classes from HTML elements

2. **Add Terminal CSS**:
   - Add CDN link: `<link rel="stylesheet" href="https://unpkg.com/terminal.css" />`
   - Terminal CSS is CLASSLESS - styles semantic HTML automatically

3. **Restructure HTML**:
   - Convert `<div class="...">` to semantic HTML (`<section>`, `<article>`, `<header>`, etc.)
   - Rely on Terminal CSS's default styling for base elements
   - Keep custom CSS for:
     * Gradient progress bars (critical feature)
     * Animations (shimmer, pulse)
     * Token gauges
     * Multi-agent cards
     * Status indicators

4. **Custom CSS Strategy**:
   - Keep existing keyframes and animations
   - Adapt color scheme to Terminal CSS theme (green-on-black retro)
   - Maintain all gradient effects
   - Ensure responsive layouts work

5. **Layout Adaptation**:
   - Replace Tailwind grid classes with custom grid CSS or Terminal CSS layout
   - Maintain 3-column desktop / 1-column mobile layout
   - Keep all panels and sections visible

6. **JavaScript**:
   - NO CHANGES to JavaScript code (lines 413-1051)
   - All functionality must remain intact
   - WebSocket, API calls, rendering functions unchanged

## Risks

### High Risk
- **Breaking multi-agent monitoring**: Complex layout with progress bars and token gauges
- **Loss of gradient animations**: Custom animations must be preserved
- **Responsive layout issues**: Terminal CSS may not have built-in grid system
- **Color scheme mismatch**: Need to ensure good contrast and readability

### Medium Risk
- **Button/form styling**: Terminal CSS styles may not match expectations
- **Spacing issues**: Tailwind's utility spacing vs Terminal CSS defaults
- **WebSocket updates triggering layout shifts**: Ensure smooth transitions

### Low Risk
- **Log viewer**: Simple monospace styling, should work fine
- **Session selector**: Standard dropdown, Terminal CSS handles it

## Prevention Strategy

### Before Implementation
1. **Study Terminal CSS docs**: Understand its classless approach and available CSS variables
2. **Plan semantic HTML structure**: Map current Tailwind components to semantic equivalents
3. **Identify custom CSS requirements**: Extract what Terminal CSS won't cover

### During Implementation
1. **Preserve all custom animations**: Copy keyframes verbatim
2. **Test incrementally**: Ensure each section renders before moving to next
3. **Maintain JavaScript untouched**: Only modify HTML/CSS

### Testing
1. **Visual regression**: Compare layouts side-by-side
2. **Functional testing**: All buttons, dropdowns, WebSocket updates work
3. **Responsive testing**: Mobile and desktop layouts
4. **Animation testing**: Progress bars animate smoothly
5. **Real data testing**: Test with actual session data if possible

## Success Criteria
- ✅ Zero Tailwind CSS references remain
- ✅ Terminal CSS loaded via CDN
- ✅ All multi-agent monitoring features work
- ✅ Gradient progress bars animate correctly
- ✅ Token gauges show color warnings
- ✅ WebSocket updates trigger UI changes
- ✅ Retro terminal aesthetic achieved
- ✅ Responsive on desktop and mobile
- ✅ All JavaScript functionality preserved
- ✅ Clean, semantic HTML structure
