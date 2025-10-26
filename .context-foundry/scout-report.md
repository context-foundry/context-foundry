# Scout Report: Documentation Site Fixes

## Executive Summary

The Context Foundry documentation site at `/docs/` has three critical bugs preventing it from functioning:

1. **Missing Fuse.js library** - Search stays on "loading..." forever
2. **Empty sidebar navigation** - Sidebar HTML exists but is unpopulated
3. **404 error** - Reference to non-existent `/docs/assets/search.js`

All three issues are straightforward fixes requiring JavaScript library loading and navigation population logic.

## Requirements Analysis

### Critical Fixes Required

**Issue #1: Search Functionality Broken**
- **Problem**: `docs.js` expects `window.Fuse` but Fuse.js is never loaded
- **Location**: Line 78-86 in `/public/docs/assets/docs.js`
- **Impact**: Search displays "search index loading..." permanently
- **Fix**: Add Fuse.js CDN script tag before docs.js loads

**Issue #2: Sidebar Navigation Empty**
- **Problem**: Sidebar HTML is rendered but contains NO content
  - Category titles are empty: `<h2 class="sidebar-category-title"></h2>`
  - Category lists are empty: `<ul class="sidebar-category-list">`
  - Breadcrumbs are empty: `<span itemprop="name"></span>`
- **Root cause**: No JavaScript loads `/docs/assets/navigation.json` and populates the DOM
- **Data exists**: `navigation.json` has complete navigation structure
- **Fix**: Add JavaScript to fetch navigation.json and populate sidebar/breadcrumbs

**Issue #3: 404 Error - Missing search.js**
- **Problem**: HTML references `/docs/assets/search.js` which doesn't exist
- **Location**: Line 370 in `/public/docs/index.html`
- **Actual file**: Only `/docs/assets/docs.js` exists (which handles search)
- **Fix**: Remove incorrect script tag (search is already in docs.js)

## Technology Stack

**Current Stack:**
- Pure HTML/CSS/JavaScript (no framework)
- Fuse.js for fuzzy search (needs to be added via CDN)
- Prism.js for syntax highlighting (already loaded)
- Static site served from `/public/` directory

**Recommended Approach:**
- Add Fuse.js 6.6.2 from CDN (before docs.js)
- Create navigation loader in docs.js to populate sidebar
- Remove duplicate/incorrect script references
- Test in real browser (already running on localhost:8080)

## File Inventory

**Files requiring updates:**
- `/public/docs/index.html` - Fix script tags
- `/public/docs/getting-started/*.html` (4 files) - Add Fuse.js
- `/public/docs/guides/*.html` (4 files) - Add Fuse.js  
- `/public/docs/technical/*.html` (5 files) - Add Fuse.js
- `/public/docs/reference/*.html` (3 files) - Add Fuse.js
- `/public/docs/assets/docs.js` - Add navigation loader

**Total**: 17 HTML files + 1 JS file = 18 file modifications

## Architecture Recommendations

### 1. Script Loading Order (CRITICAL)
```html
<!-- In all doc pages, before closing </body>: -->
<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>
<script src="/docs/assets/docs.js" defer></script>
<!-- Remove: <script src="/docs/assets/search.js" defer></script> -->
```

### 2. Navigation Population Logic
Add to docs.js `init()` function:
- `initNavigation()` - Fetch navigation.json and populate sidebar
- `initBreadcrumbs()` - Populate breadcrumbs based on current URL
- Run before other initializers that depend on navigation

### 3. Implementation Strategy
**Phase 1**: Fix script loading (Fuse.js + remove search.js)
**Phase 2**: Add navigation population JavaScript  
**Phase 3**: Test search, sidebar, and breadcrumbs
**Phase 4**: Verify responsive mobile behavior

## Testing Requirements

### Manual Testing Checklist
- [ ] Open http://localhost:8080/docs/ - no console errors
- [ ] Open http://localhost:8080/docs/getting-started/quickstart - sidebar visible
- [ ] Click sidebar links - navigation works
- [ ] Type in search box - results appear
- [ ] Search for "scout" - finds relevant docs
- [ ] Mobile view (< 968px) - hamburger menu shows sidebar
- [ ] Test on Chrome, Firefox, Safari
- [ ] Verify no 404 errors in browser console

### Edge Cases
- Search with < 3 characters - should clear results
- Search with no matches - should show "No results"
- Mobile menu outside click - should close sidebar
- Escape key - should close search/mobile menu

## Challenges & Mitigations

**Challenge #1**: 21 HTML files to update
- **Mitigation**: Use template/pattern for script tags, apply consistently
- **Verification**: Glob pattern to find all HTML files, update systematically

**Challenge #2**: Navigation population timing
- **Mitigation**: Fetch navigation.json in init(), populate synchronously before other features
- **Error handling**: Log error if navigation.json fails, degrade gracefully

**Challenge #3**: Testing in real browser
- **Mitigation**: Server already running on port 8080, test incrementally
- **Rollback**: Git working directory is NOT clean, create feature branch first

## Timeline Estimate

- **Script tag fixes**: 10 minutes (straightforward find/replace)
- **Navigation JavaScript**: 20 minutes (new code, testing)
- **Browser testing**: 15 minutes (verify all features work)
- **Fixes/refinements**: 15 minutes (handle edge cases)

**Total**: ~60 minutes

## Success Criteria

1. ✅ Browser console shows ZERO 404 errors
2. ✅ Sidebar displays all 4 navigation categories with links
3. ✅ Search returns results and highlights matches
4. ✅ Breadcrumbs show current page hierarchy
5. ✅ Mobile menu toggle works correctly
6. ✅ All 21 HTML pages load without errors

---

**Scout Phase Complete** - Ready for Architect to design implementation strategy.
