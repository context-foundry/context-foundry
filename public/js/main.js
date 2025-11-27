/**
 * Main JavaScript functionality
 * Handles smooth scrolling, copy-to-clipboard, and scroll animations
 */

(function() {
  'use strict';

  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    initRotatingTagline();
    initRotatingExamples();
    initSmoothScroll();
    initCopyButtons();
    initScrollAnimations();
    initExternalLinks();
    initDynamicVersion();
  }

  /**
   * Rotate through hero taglines with fade animation
   */
  function initRotatingTagline() {
    console.log('[Rotation] Starting initialization...');

    const taglines = [
      'while you sleep',
      'while you grab coffee',
      'while you doom scroll',
      'while you walk the dog',
      'while you review PRs',
      'while you touch grass',
      'while you read Hacker News',
      'while you fix your vim config',
      'while you yak shave',
      'while you explain what you do to your parents',
      'while you actually read the docs',
      'while you solve today\'s Wordle',
      'while the daemon works',
      'with BAML-structured outputs',
      'while agents self-improve',
      'while tests fix themselves',
      'during your standup',
      'while you debate tabs vs spaces',
      'while patterns learn themselves',
      'while 8 builders run in parallel',
      'with fresh 200K token windows',
      'while the job queue persists',
      'while schemas validate themselves',
      'while you ship actual features',
      'while context stays clean'
    ];

    const taglineElement = document.getElementById('rotating-tagline');
    if (!taglineElement) {
      console.error('[Rotation] Element #rotating-tagline not found!');
      return;
    }
    console.log('[Rotation] Element found:', taglineElement);

    // Start with first tagline
    let currentIndex = 0;
    taglineElement.textContent = taglines[currentIndex];
    console.log('[Rotation] Set initial tagline:', taglines[currentIndex]);

    // Rotate every 3 seconds
    setInterval(function() {
      console.log('[Rotation] Rotating to next tagline...');
      // Fade out
      taglineElement.style.opacity = '0';

      setTimeout(function() {
        // Move to next tagline
        currentIndex = (currentIndex + 1) % taglines.length;
        taglineElement.textContent = taglines[currentIndex];
        console.log('[Rotation] Now showing:', taglines[currentIndex]);

        // Fade in
        taglineElement.style.opacity = '1';
      }, 300);
    }, 3000);

    console.log('[Rotation] setInterval established, will rotate every 3 seconds');
  }

  /**
   * Rotate through build examples with fade animation
   */
  function initRotatingExamples() {
    const examples = [
      'Use CF to build a mass text messaging app',
      'Use CF to build a real-time stock portfolio tracker',
      'Use CF to build a multiplayer trivia game with WebSockets',
      'Use CF to build a CLI tool for managing Docker containers',
      'Use CF to build a recipe finder with dietary filters',
      'Use CF to build a markdown blog with syntax highlighting',
      'Use CF to build a kanban board with drag-and-drop',
      'Use CF to build an invoice generator with PDF export',
      'Use CF to build a habit tracker with streak notifications',
      'Use CF to build a URL shortener with analytics',
      'Use CF to build a weather dashboard with 5-day forecast',
      'Use CF to build a pomodoro timer with ambient sounds'
    ];

    const exampleElement = document.getElementById('rotating-example');
    if (!exampleElement) {
      return;
    }

    let currentIndex = 0;
    exampleElement.textContent = examples[currentIndex];

    // Rotate every 4 seconds (slightly slower than hero tagline)
    setInterval(function() {
      exampleElement.style.opacity = '0';

      setTimeout(function() {
        currentIndex = (currentIndex + 1) % examples.length;
        exampleElement.textContent = examples[currentIndex];
        exampleElement.style.opacity = '1';
      }, 300);
    }, 4000);
  }

  /**
   * Smooth scroll to anchor links
   */
  function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach(function(link) {
      link.addEventListener('click', function(event) {
        const href = link.getAttribute('href');

        // Skip empty hash
        if (href === '#') {
          event.preventDefault();
          return;
        }

        const target = document.querySelector(href);

        if (target) {
          event.preventDefault();

          const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
          const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight;

          window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
          });

          // Update URL without scrolling
          if (history.pushState) {
            history.pushState(null, null, href);
          }
        }
      });
    });
  }

  /**
   * Copy code to clipboard functionality
   */
  function initCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-button');

    copyButtons.forEach(function(button) {
      button.addEventListener('click', function() {
        const codeText = button.getAttribute('data-copy');

        if (!codeText) {
          console.warn('No code to copy');
          return;
        }

        // Use Clipboard API if available
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(codeText)
            .then(function() {
              showCopyFeedback(button);
            })
            .catch(function(err) {
              console.error('Failed to copy:', err);
              fallbackCopy(codeText, button);
            });
        } else {
          fallbackCopy(codeText, button);
        }
      });
    });
  }

  /**
   * Fallback copy method for older browsers
   */
  function fallbackCopy(text, button) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
      document.execCommand('copy');
      showCopyFeedback(button);
    } catch (err) {
      console.error('Fallback copy failed:', err);
    }

    document.body.removeChild(textarea);
  }

  /**
   * Show visual feedback when code is copied
   */
  function showCopyFeedback(button) {
    const originalHTML = button.innerHTML;

    button.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    button.classList.add('copied');

    setTimeout(function() {
      button.innerHTML = originalHTML;
      button.classList.remove('copied');
    }, 2000);
  }

  /**
   * Intersection Observer for scroll animations
   */
  function initScrollAnimations() {
    // Check if IntersectionObserver is supported
    if (!('IntersectionObserver' in window)) {
      return; // Skip animations on older browsers
    }

    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in');
          observer.unobserve(entry.target); // Only animate once
        }
      });
    }, observerOptions);

    // Observe elements that should animate on scroll
    const animateElements = document.querySelectorAll('.feature-card, .pipeline-stage, .quickstart-step, .metric-card');

    animateElements.forEach(function(el) {
      observer.observe(el);
    });
  }

  /**
   * Add security attributes to external links
   */
  function initExternalLinks() {
    const links = document.querySelectorAll('a[target="_blank"]');

    links.forEach(function(link) {
      // Ensure noopener and noreferrer for security
      const rel = link.getAttribute('rel') || '';
      const relParts = rel.split(' ').filter(function(part) { return part; });

      if (relParts.indexOf('noopener') === -1) {
        relParts.push('noopener');
      }
      if (relParts.indexOf('noreferrer') === -1) {
        relParts.push('noreferrer');
      }

      link.setAttribute('rel', relParts.join(' '));
    });
  }

  /**
   * Fetch version from npm registry and update footer
   * Falls back to static version if fetch fails
   */
  function initDynamicVersion() {
    const versionElement = document.getElementById('footer-version');
    if (!versionElement) {
      return;
    }

    // Fetch latest version from npm registry
    fetch('https://registry.npmjs.org/context-foundry/latest')
      .then(function(response) {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(function(data) {
        if (data.version) {
          versionElement.textContent = 'Version ' + data.version;
        }
      })
      .catch(function(error) {
        // Keep static version on error - no console.error to avoid noise
      });
  }

})();
