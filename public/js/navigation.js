/**
 * Mobile Navigation Toggle
 * Handles opening/closing the mobile menu with accessibility support
 */

(function() {
  'use strict';

  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavigation);
  } else {
    initNavigation();
  }

  function initNavigation() {
    const toggle = document.querySelector('.mobile-menu-toggle');
    const menu = document.querySelector('.nav-menu');
    const body = document.body;

    if (!toggle || !menu) {
      console.warn('Navigation elements not found');
      return;
    }

    // Toggle menu function
    function toggleMenu() {
      const isOpen = menu.classList.contains('active');

      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    }

    // Open menu
    function openMenu() {
      menu.classList.add('active');
      toggle.classList.add('active');
      toggle.setAttribute('aria-expanded', 'true');
      body.style.overflow = 'hidden'; // Prevent scrolling when menu is open
    }

    // Close menu
    function closeMenu() {
      menu.classList.remove('active');
      toggle.classList.remove('active');
      toggle.setAttribute('aria-expanded', 'false');
      body.style.overflow = ''; // Restore scrolling
    }

    // Click on toggle button
    toggle.addEventListener('click', toggleMenu);

    // Click on menu links (close menu after navigation)
    const menuLinks = menu.querySelectorAll('.nav-link');
    menuLinks.forEach(function(link) {
      link.addEventListener('click', function() {
        // Small delay to allow smooth scroll to start
        setTimeout(closeMenu, 100);
      });
    });

    // Click outside menu to close
    document.addEventListener('click', function(event) {
      const isClickInsideMenu = menu.contains(event.target);
      const isClickOnToggle = toggle.contains(event.target);

      if (!isClickInsideMenu && !isClickOnToggle && menu.classList.contains('active')) {
        closeMenu();
      }
    });

    // Escape key to close
    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape' && menu.classList.contains('active')) {
        closeMenu();
      }
    });

    // Close menu on window resize (if opened on mobile, then resized to desktop)
    let resizeTimer;
    window.addEventListener('resize', function() {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function() {
        if (window.innerWidth >= 768 && menu.classList.contains('active')) {
          closeMenu();
        }
      }, 250);
    });
  }

})();
