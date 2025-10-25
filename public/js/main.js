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
    initSmoothScroll();
    initCopyButtons();
    initScrollAnimations();
    initExternalLinks();
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

})();
