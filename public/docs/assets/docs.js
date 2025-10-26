/**
 * Context Foundry Documentation - Main JavaScript
 * Handles UI interactions, search, mobile menu, and theme toggle
 */

(function() {
  'use strict';

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    initMobileMenu();
    initSearch();
    initThemeToggle();
    initSidebarCollapse();
    initTOCHighlight();
    initCodeCopyButtons();
    initSmoothScroll();
  }

  /**
   * Mobile Menu Toggle
   */
  function initMobileMenu() {
    const toggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('docs-sidebar');

    if (!toggle || !sidebar) return;

    toggle.addEventListener('click', () => {
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', !isExpanded);
      sidebar.setAttribute('aria-expanded', !isExpanded);
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar.getAttribute('aria-expanded') === 'true') {
        toggle.setAttribute('aria-expanded', 'false');
        sidebar.setAttribute('aria-expanded', 'false');
      }
    });

    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (sidebar.getAttribute('aria-expanded') === 'true' &&
          !sidebar.contains(e.target) &&
          !toggle.contains(e.target)) {
        toggle.setAttribute('aria-expanded', 'false');
        sidebar.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /**
   * Search Functionality (loads search-index.json and uses Fuse.js)
   */
  function initSearch() {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');

    if (!searchInput || !searchResults) return;

    let fuse = null;
    let searchIndex = null;

    // Load search index
    fetch('/docs/assets/search-index.json')
      .then(res => res.json())
      .then(data => {
        searchIndex = data;
        // Fuse.js will be loaded from CDN in HTML
        if (window.Fuse) {
          fuse = new window.Fuse(searchIndex, {
            keys: ['title', 'content', 'category'],
            threshold: 0.3,
            ignoreLocation: true,
            minMatchCharLength: 3,
          });
        }
      })
      .catch(err => console.error('Failed to load search index:', err));

    // Search on input
    searchInput.addEventListener('input', debounce((e) => {
      const query = e.target.value.trim();

      if (query.length < 3) {
        searchResults.innerHTML = '';
        searchResults.setAttribute('aria-expanded', 'false');
        return;
      }

      if (!fuse) {
        searchResults.innerHTML = '<div style="padding: 1rem; color: #8b949e;">Search index loading...</div>';
        searchResults.setAttribute('aria-expanded', 'true');
        return;
      }

      const results = fuse.search(query).slice(0, 10);

      if (results.length === 0) {
        searchResults.innerHTML = '<div style="padding: 1rem; color: #8b949e;">No results found</div>';
        searchResults.setAttribute('aria-expanded', 'true');
        return;
      }

      searchResults.innerHTML = results.map(result => {
        const item = result.item;
        return `
          <a href="${item.url}" class="search-result-item" style="
            display: block;
            padding: 0.75rem 1rem;
            text-decoration: none;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
          " onmouseover="this.style.background='rgba(88, 166, 255, 0.1)'"
             onmouseout="this.style.background='transparent'">
            <div style="font-weight: 500; color: #e6edf3; margin-bottom: 0.25rem;">
              ${escapeHtml(item.title)}
            </div>
            <div style="font-size: 0.8125rem; color: #8b949e;">
              ${escapeHtml(item.category || '')} ${item.excerpt ? '• ' + escapeHtml(item.excerpt.substring(0, 100)) + '...' : ''}
            </div>
          </a>
        `;
      }).join('');

      searchResults.setAttribute('aria-expanded', 'true');
    }, 300));

    // Keyboard navigation (⌘K to focus search)
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
      }

      if (e.key === 'Escape' && document.activeElement === searchInput) {
        searchInput.blur();
        searchResults.setAttribute('aria-expanded', 'false');
      }
    });

    // Close results when clicking outside
    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /**
   * Theme Toggle
   */
  function initThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    toggle.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
    });

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }

  /**
   * Sidebar Category Collapse
   */
  function initSidebarCollapse() {
    const toggles = document.querySelectorAll('.sidebar-category-toggle');

    toggles.forEach(toggle => {
      toggle.addEventListener('click', () => {
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', !isExpanded);

        const targetId = toggle.getAttribute('aria-controls');
        const target = document.getElementById(targetId);
        if (target) {
          target.style.display = isExpanded ? 'none' : 'block';
        }
      });
    });
  }

  /**
   * Table of Contents Highlight on Scroll
   */
  function initTOCHighlight() {
    const tocLinks = document.querySelectorAll('.docs-toc a');
    if (tocLinks.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          tocLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${id}`) {
              link.classList.add('active');
            }
          });
        }
      });
    }, { rootMargin: '-100px 0px -66%' });

    document.querySelectorAll('.docs-article h2[id], .docs-article h3[id]').forEach(heading => {
      observer.observe(heading);
    });
  }

  /**
   * Add Copy Buttons to Code Blocks
   */
  function initCodeCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code');

    codeBlocks.forEach(block => {
      const button = document.createElement('button');
      button.className = 'copy-code-button';
      button.textContent = 'Copy';
      button.style.cssText = `
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        padding: 0.375rem 0.75rem;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        color: #e6edf3;
        font-size: 0.75rem;
        cursor: pointer;
        transition: all 0.2s;
      `;

      button.addEventListener('click', () => {
        navigator.clipboard.writeText(block.textContent).then(() => {
          button.textContent = 'Copied!';
          setTimeout(() => {
            button.textContent = 'Copy';
          }, 2000);
        });
      });

      const pre = block.parentElement;
      pre.style.position = 'relative';
      pre.appendChild(button);
    });
  }

  /**
   * Smooth Scroll to Anchors
   */
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href === '#') return;

        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          history.pushState(null, null, href);
        }
      });
    });
  }

  /**
   * Utility: Debounce function
   */
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Utility: Escape HTML
   */
  function escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

})();
