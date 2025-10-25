# Scout Report: Tailwind → Terminal CSS Migration

## Executive Summary
**Task**: Replace Tailwind CSS with Terminal CSS in the Context Foundry livestream dashboard while preserving all functionality and achieving a retro terminal aesthetic.

**Complexity**: Medium-High
- Extensive custom styling must be preserved
- Complex multi-agent monitoring UI with gradients and animations
- WebSocket-driven real-time updates require stable DOM structure
- No backend changes needed

**Recommendation**: PROCEED with careful HTML restructuring and custom CSS preservation strategy.

## Technology Stack Decision

### Target Framework: Terminal CSS v0.7.4
- **CDN**: `https://unpkg.com/terminal.css@0.7.4/dist/terminal.min.css`
- **Type**: Classless CSS framework (styles semantic HTML automatically)
- **Size**: ~3KB gzipped (extremely lightweight)
- **Philosophy**: Retro terminal aesthetic with monospace fonts
- **Theming**: CSS variables for customization

### Why Terminal CSS?
✅ Perfect retro terminal aesthetic (matches Context Foundry's hacker vibe)
✅ Classless approach = cleaner semantic HTML
✅ Monospace fonts already used in current dashboard
✅ Lightweight (vs Tailwind's large footprint)
✅ CSS variables for easy customization
✅ No build process required (CDN)

## Requirements Analysis

### MUST PRESERVE (Critical Features)
1. **Multi-agent monitoring panel**
   - Per-agent gradient progress bars with shimmer animation
   - Token usage gauges with color warnings (green/yellow/red)
   - Real-time status indicators (● active/idle/completed)
   - Agent cards with hover effects

2. **Progress visualizations**
   - Horizontal gradient bars (green → yellow → red)
   - Percentage overlays
   - Smooth width transitions (CSS transitions)
   - Shimmer/pulse animations

3. **WebSocket functionality**
   - All JavaScript code unchanged
   - Real-time updates trigger DOM updates
   - Auto-reconnect logic
   - Phase update handling

4. **Layout structure**
   - 3-column grid on desktop
   - Single column on mobile
   - Session selector dropdown
   - Live logs viewer with auto-scroll

5. **Custom animations**
   - @keyframes shimmer (progress bars)
   - @keyframes pulse-red (critical warnings)
   - @keyframes pulse (token warnings)
   - Hover effects on metric cards

### Terminal CSS Capabilities

**What Terminal CSS provides automatically:**
- Semantic HTML styling (header, section, article, nav, etc.)
- Form elements (select, input, button, textarea)
- Typography (headings, paragraphs, monospace code blocks)
- Tables, lists, blockquotes
- Alert components (via optional classes)
- Basic buttons (default, primary, error)

**What requires custom CSS:**
- Grid layouts (Terminal CSS has NO built-in grid)
- Progress bars with gradients (Terminal CSS has basic progress bars only)
- Multi-agent cards with animations
- Token gauges
- Phase indicator backgrounds
- Hover effects and transitions
- Status indicator colors

## Architecture Recommendations

### 1. HTML Structure Strategy

**Replace Tailwind utility classes with semantic HTML:**

```html
<!-- BEFORE (Tailwind) -->
<div class="mb-6 bg-gray-900 p-4 rounded-lg">
  <label class="block text-sm font-bold mb-2">Active Session:</label>
  <select id="sessionSelector" class="w-full bg-gray-800 text-white p-2 rounded">
  </select>
</div>

<!-- AFTER (Terminal CSS + Custom) -->
<section class="session-selector">
  <label for="sessionSelector">Active Session:</label>
  <select id="sessionSelector">
    <option>Loading sessions...</option>
  </select>
</section>
```

**Use semantic elements:**
- `<header>` for page title
- `<section>` for major panels
- `<article>` for agent cards
- `<nav>` for action buttons
- `<aside>` for statistics sidebar

### 2. Custom CSS Strategy

**Preserve all existing custom CSS (lines 19-149):**
- Phase gradients (.phase-scout, .phase-architect, etc.)
- Agent progress bars with shimmer
- Token gauges with gradients
- Keyframe animations
- Hover effects

**Add new custom CSS for layout:**
```css
/* Grid layout (Terminal CSS has none) */
.dashboard-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
```

**Override Terminal CSS defaults where needed:**
```css
/* Adjust Terminal CSS color scheme */
:root {
  --background-color: #0a0a0a;
  --font-color: #00ff00;
  --primary-color: #00ff00;
  --secondary-color: #33ff33;
  --block-background-color: #111111;
}
```

### 3. Color Scheme Adaptation

**Terminal CSS Default Theme**: Light mode with blue accents
**Our Customization**: Dark green-on-black retro terminal

**CSS Variables to override:**
- `--background-color: #0a0a0a` (almost black)
- `--font-color: #00ff00` (terminal green)
- `--primary-color: #00ff00` (green for buttons)
- `--secondary-color: #33ff33` (lighter green)
- `--block-background-color: #111111` (dark panels)
- `--invert-font-color: #000000` (for buttons)

**Keep custom colors:**
- Status indicators (green #10b981, yellow #eab308, red #ef4444)
- Phase gradients (purple, pink, blue, green)
- Token gauge gradient (green → yellow → red)

### 4. Layout Migration Plan

**Grid replacement:**
```css
/* Replace: grid grid-cols-1 lg:grid-cols-3 gap-6 */
.main-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
}

@media (min-width: 1024px) {
  .main-grid {
    grid-template-columns: 2fr 1fr;
  }
}
```

**Spacing system:**
- Terminal CSS uses `--global-space: 10px`
- Current dashboard uses Tailwind spacing (p-4 = 1rem, p-6 = 1.5rem)
- Solution: Add custom padding/margin classes or inline styles

### 5. Component Mapping

| Current (Tailwind) | Terminal CSS Equivalent |
|-------------------|------------------------|
| `<select class="...">` | `<select>` (auto-styled) |
| `<button class="bg-blue-600...">` | `<button class="btn-primary">` |
| `<div class="bg-gray-900 p-6 rounded-lg">` | `<section>` + custom .panel class |
| `<h1 class="text-4xl font-bold">` | `<h1>` (auto-styled) |
| `<div class="grid grid-cols-3 gap-4">` | Custom .stats-grid class |

## Challenges and Mitigations

### Challenge 1: No Built-in Grid System
**Impact**: High - Dashboard relies heavily on grid layouts
**Mitigation**: 
- Create custom grid CSS classes
- Use CSS Grid with media queries for responsive design
- Test layouts at multiple breakpoints

### Challenge 2: Complex Progress Bars
**Impact**: High - Multi-agent monitoring is a key feature
**Mitigation**:
- Keep ALL existing progress bar CSS
- Ensure gradients and animations are preserved
- Test shimmer animation still works
- Verify percentage overlays display correctly

### Challenge 3: Color Scheme Consistency
**Impact**: Medium - Terminal CSS defaults may conflict
**Mitigation**:
- Override Terminal CSS variables in custom CSS
- Test color contrast for accessibility
- Ensure status indicators remain visible
- Preserve warning colors (green/yellow/red)

### Challenge 4: Button Styling
**Impact**: Low - Terminal CSS provides button classes
**Mitigation**:
- Use `class="btn-primary"` for primary actions
- Use `class="btn-ghost"` for secondary actions
- Add custom hover effects if needed

### Challenge 5: Form Elements
**Impact**: Low - Terminal CSS auto-styles forms
**Mitigation**:
- Session selector dropdown should work automatically
- May need custom styling to match dark theme
- Test dropdown visibility and usability

## Testing Strategy

### Phase 1: Visual Testing (Manual)
1. Open dashboard in browser
2. Verify Terminal CSS loaded (check Network tab)
3. Check all panels render correctly
4. Verify gradient progress bars animate
5. Test responsive layout (resize window)
6. Verify color scheme matches retro terminal aesthetic

### Phase 2: Functional Testing
1. **Session selector**: Change sessions, verify WebSocket reconnects
2. **Live logs**: Check auto-scroll and emoji highlighting
3. **Multi-agent panel**: Verify agent cards render and update
4. **Progress bars**: Trigger update, verify smooth transitions
5. **Token gauges**: Check color warnings (50%, 75%, 100%)
6. **Export button**: Verify JSON export works
7. **Refresh button**: Verify manual refresh works

### Phase 3: Integration Testing
1. Start livestream server
2. Trigger phase update via API
3. Verify dashboard updates in real-time
4. Check WebSocket auto-reconnect after disconnect
5. Test with multiple agents active simultaneously

### Success Criteria
- ✅ Zero Tailwind references in HTML
- ✅ Terminal CSS CDN loaded successfully
- ✅ All multi-agent monitoring features functional
- ✅ Gradient progress bars animate smoothly
- ✅ Token gauges show correct colors
- ✅ WebSocket updates work
- ✅ Retro terminal aesthetic achieved
- ✅ Responsive on mobile and desktop
- ✅ No JavaScript errors in console
- ✅ All buttons and forms work

## Implementation Estimate

**Complexity Breakdown:**
- HTML restructuring: 2-3 hours (1,053 lines)
- Custom CSS adaptation: 1-2 hours
- Testing and debugging: 1-2 hours
- Total: 4-7 hours

**Risk Level**: MEDIUM
- Most risk in layout migration (no grid system)
- Low risk in functionality (JavaScript unchanged)
- Medium risk in visual consistency

## Recommendations

### DO:
✅ Preserve ALL existing custom CSS for animations
✅ Use semantic HTML throughout
✅ Override Terminal CSS variables for dark theme
✅ Create custom grid classes for layouts
✅ Test incrementally (section by section)
✅ Keep JavaScript 100% unchanged

### DON'T:
❌ Don't remove gradient animations
❌ Don't change WebSocket logic
❌ Don't rely solely on Terminal CSS for complex layouts
❌ Don't skip responsive testing
❌ Don't forget to test with real session data

## Next Steps → Architect Phase

The Architect should:
1. Create detailed HTML structure with semantic elements
2. Design custom CSS for grid layouts
3. Plan CSS variable overrides for Terminal CSS theme
4. Map each Tailwind component to Terminal CSS equivalent
5. Create comprehensive test plan
6. Document all custom CSS requirements
