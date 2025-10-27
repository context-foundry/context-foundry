# Architecture: Documentation Site Fixes

## System Overview

This fix addresses three critical bugs in the Context Foundry documentation site through targeted modifications to HTML script loading and JavaScript initialization logic.

**Fix Categories:**
1. Library loading (Fuse.js CDN)
2. Script reference correction (remove non-existent search.js)
3. Navigation population (fetch and render navigation.json)

## Complete File Structure

```
public/
├── docs/
│   ├── index.html                    [FIX: Remove search.js reference]
│   ├── assets/
│   │   ├── docs.js                   [MODIFY: Add navigation loader]
│   │   ├── docs.css                  [NO CHANGE]
│   │   ├── search-index.json         [NO CHANGE]
│   │   └── navigation.json           [NO CHANGE]
│   ├── getting-started/
│   │   ├── index.html                [FIX: Add Fuse.js]
│   │   ├── faq.html                  [FIX: Add Fuse.js]
│   │   ├── quickstart.html           [FIX: Add Fuse.js]
│   │   ├── readme.html               [FIX: Add Fuse.js]
│   │   └── user-guide.html           [FIX: Add Fuse.js]
│   ├── guides/
│   │   ├── index.html                [FIX: Add Fuse.js]
│   │   ├── changelog.html            [FIX: Add Fuse.js]
│   │   ├── feedback-system.html      [FIX: Add Fuse.js]
│   │   ├── roadmap.html              [FIX: Add Fuse.js]
│   │   └── security.html             [FIX: Add Fuse.js]
│   ├── technical/
│   │   ├── index.html                [FIX: Add Fuse.js]
│   │   ├── innovations.html          [FIX: Add Fuse.js]
│   │   ├── architecture-diagrams.html [FIX: Add Fuse.js]
│   │   ├── context-preservation.html [FIX: Add Fuse.js]
│   │   ├── delegation-model.html     [FIX: Add Fuse.js]
│   │   └── mcp-server-architecture.html [FIX: Add Fuse.js]
│   └── reference/
│       ├── index.html                [FIX: Add Fuse.js]
│       ├── architecture-decisions.html [FIX: Add Fuse.js]
│       ├── claude-code-mcp-setup.html [FIX: Add Fuse.js]
│       └── technical-faq.html        [FIX: Add Fuse.js]
```

**Files to modify**: 21 HTML files + 1 JS file = 22 total

## Module Specifications

### Module 1: HTML Script Tag Fixes (20 files)

**Purpose**: Add Fuse.js library and remove incorrect script reference

**Files affected**: All doc pages EXCEPT `/public/docs/index.html`

**Current state (BROKEN)**:
```html
<!-- Near end of <body>, typical doc page -->
<script src="/docs/assets/search.js" defer></script>  <!-- 404! File doesn't exist -->
<script src="/docs/assets/docs.js" defer></script>
```

**Target state (FIXED)**:
```html
<!-- Near end of <body>, typical doc page -->
<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>
<script src="/docs/assets/docs.js" defer></script>
```

**Implementation**:
1. Find all HTML files: `find public/docs -name "*.html" -type f`
2. For each file (except index.html):
   - Locate script tags near closing `</body>`
   - Add Fuse.js CDN before docs.js
   - Remove search.js reference if present
   - Keep Prism.js reference if present

### Module 2: Index Page Script Fix (1 file)

**Purpose**: Remove non-existent search.js from docs index page

**File**: `/public/docs/index.html`

**Current state (BROKEN)**:
```html
<!-- Line 370 -->
<script src="/docs/assets/search.js" defer></script>
<script src="/docs/assets/docs.js" defer></script>
```

**Target state (FIXED)**:
```html
<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>
<script src="/docs/assets/docs.js" defer></script>
```

### Module 3: Navigation Population JavaScript (1 file)

**Purpose**: Load navigation.json and populate sidebar + breadcrumbs

**File**: `/public/docs/assets/docs.js`

**NEW CODE TO ADD**:

```javascript
// Add to init() function (line 16):
initNavigation();
initBreadcrumbs();

// Add new functions before closing IIFE:

/**
 * Navigation Loader - Populates Sidebar from navigation.json
 */
function initNavigation() {
  const sidebar = document.getElementById('docs-sidebar');
  if (!sidebar) return; // Not on a page with sidebar

  fetch('/docs/assets/navigation.json')
    .then(res => res.json())
    .then(data => {
      const categories = data.categories;
      const sidebarNav = sidebar.querySelector('.sidebar-nav');
      
      // Clear existing empty categories
      sidebarNav.innerHTML = '';
      
      // Populate each category
      categories.forEach(category => {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'sidebar-category';
        categoryDiv.setAttribute('data-category', category.id);
        
        // Category toggle button
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'sidebar-category-toggle';
        button.setAttribute('aria-expanded', 'true');
        button.setAttribute('aria-controls', `sidebar-category-${category.id}`);
        button.innerHTML = `
          <svg class="sidebar-category-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M6 4L10 8L6 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h2 class="sidebar-category-title">${category.name}</h2>
        `;
        
        // Category list
        const ul = document.createElement('ul');
        ul.className = 'sidebar-category-list';
        ul.id = `sidebar-category-${category.id}`;
        
        category.docs.forEach(doc => {
          const li = document.createElement('li');
          li.className = 'sidebar-item';
          
          const a = document.createElement('a');
          a.href = doc.url;
          a.className = 'sidebar-link';
          
          // Mark current page as active
          if (window.location.pathname === doc.url || 
              window.location.pathname === doc.url + '.html') {
            a.classList.add('active');
          }
          
          a.textContent = doc.title;
          li.appendChild(a);
          ul.appendChild(li);
        });
        
        categoryDiv.appendChild(button);
        categoryDiv.appendChild(ul);
        sidebarNav.appendChild(categoryDiv);
      });
      
      // Re-initialize collapse handlers
      initSidebarCollapse();
    })
    .catch(err => console.error('Failed to load navigation:', err));
}

/**
 * Breadcrumbs Loader - Populates breadcrumbs based on current URL
 */
function initBreadcrumbs() {
  const breadcrumbsList = document.querySelector('.breadcrumbs-list');
  if (!breadcrumbsList) return; // Not on a page with breadcrumbs
  
  fetch('/docs/assets/navigation.json')
    .then(res => res.json())
    .then(data => {
      // Parse current URL to find category and page
      const path = window.location.pathname;
      const match = path.match(/\/docs\/([^\/]+)\/([^\/]+)/);
      
      if (!match) return;
      
      const [, categoryId, pageSlug] = match;
      const category = data.categories.find(c => c.id === categoryId);
      
      if (!category) return;
      
      const page = category.docs.find(d => d.slug === pageSlug);
      
      if (!page) return;
      
      // Populate breadcrumbs
      const items = breadcrumbsList.querySelectorAll('.breadcrumbs-item');
      if (items.length >= 3) {
        // Home > Category > Page
        items[0].querySelector('span[itemprop="name"]').textContent = 'Documentation';
        items[1].querySelector('span[itemprop="name"]').textContent = category.name;
        items[2].querySelector('span[itemprop="name"]').textContent = page.title;
      }
    })
    .catch(err => console.error('Failed to load breadcrumbs:', err));
}
```

**Integration points**:
- Insert `initNavigation()` and `initBreadcrumbs()` calls in `init()` function (line 16)
- Add both functions before closing `})();` at end of file
- Ensure they run BEFORE other features that depend on navigation

## Implementation Steps (Ordered)

### Step 1: Prepare Git Branch
```bash
cd /Users/name/homelab/context-foundry
git checkout -b fix/docs-site-bugs
git status  # Verify we're on the new branch
```

### Step 2: Fix Script Tags in All HTML Files

**2a. Get list of all HTML files**:
```bash
find public/docs -name "*.html" -type f > .context-foundry/html-files-list.txt
```

**2b. Fix /public/docs/index.html (special case)**:
- Read file
- Find script tags near line 370
- Remove `<script src="/docs/assets/search.js" defer></script>`
- Add `<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>` before docs.js
- Write file

**2c. Fix all other doc pages** (20 files):
For each file in list (except index.html):
- Read file
- Find script tags near closing `</body>`
- Check if Fuse.js already present (skip if so)
- Add `<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>` before docs.js
- Remove `<script src="/docs/assets/search.js" defer></script>` if present
- Write file

### Step 3: Add Navigation JavaScript

**3a. Modify /public/docs/assets/docs.js**:
- Read entire file
- Locate `init()` function (around line 16)
- Add calls to `initNavigation()` and `initBreadcrumbs()` after line 16
- Add both complete functions before closing `})();`
- Write file

### Step 4: Verify Changes

**4a. Count modified files**:
```bash
git status --short | wc -l  # Should show ~22 files
```

**4b. Preview one HTML change**:
```bash
git diff public/docs/getting-started/quickstart.html | head -50
```

**4c. Preview JavaScript change**:
```bash
git diff public/docs/assets/docs.js | head -100
```

## Testing Plan

### Unit Tests (N/A)
No unit tests for static site - all testing is integration/E2E

### Integration Tests

**Test 1: Fuse.js Loaded**
```
URL: http://localhost:8080/docs/getting-started/quickstart
Open browser console
Type: window.Fuse
Expected: function definition (not undefined)
```

**Test 2: Navigation Populated**
```
URL: http://localhost:8080/docs/getting-started/quickstart
Check: Sidebar shows 4 categories with links
Check: Breadcrumbs show "Documentation > Getting Started > Quick Start"
Expected: All content visible and clickable
```

**Test 3: Search Works**
```
URL: http://localhost:8080/docs/getting-started/quickstart
Type in search box: "scout"
Expected: Results dropdown appears with matching docs
```

**Test 4: No Console Errors**
```
URL: http://localhost:8080/docs/
Open console (F12)
Expected: Zero 404 errors, zero JavaScript errors
```

**Test 5: Mobile Menu**
```
URL: http://localhost:8080/docs/getting-started/quickstart
Resize browser to < 968px width
Click hamburger menu icon
Expected: Sidebar slides in from left
```

**Test 6: All Pages Load**
```
Test each category:
- /docs/getting-started/faq
- /docs/guides/changelog
- /docs/technical/innovations
- /docs/reference/architecture-decisions
Expected: All pages load, sidebar works, no errors
```

### Success Criteria

1. ✅ Zero 404 errors in browser console
2. ✅ Sidebar displays all categories and links
3. ✅ Search returns results for "scout", "architect", "test"
4. ✅ Breadcrumbs show correct page hierarchy
5. ✅ Mobile menu toggle works smoothly
6. ✅ All 21 HTML pages render correctly
7. ✅ `window.Fuse` is defined (library loaded)
8. ✅ Clicking sidebar links navigates correctly

## Preventive Measures

### Issue: Multiple HTML files could have inconsistent script tags
**Prevention**: Use template/pattern for all modifications, verify with git diff

### Issue: Navigation.json fetch might fail
**Prevention**: Error handling with console.error, graceful degradation

### Issue: Timing - navigation might load after other init functions
**Prevention**: Call initNavigation() and initBreadcrumbs() FIRST in init()

### Issue: Active page highlighting might not work
**Prevention**: Check both `/docs/path` and `/docs/path.html` patterns

## Deployment Steps

1. Test locally on http://localhost:8080
2. Verify all 6 integration tests pass
3. Commit changes with descriptive message
4. Push to feature branch
5. Create PR to main
6. Merge after review

---

**Architecture Complete** - Ready for Build Planning (Phase 2.5)
