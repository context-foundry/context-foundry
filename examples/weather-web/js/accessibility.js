/**
 * Accessibility manager for the weather application
 * Handles high contrast mode, focus management, and screen reader announcements
 */
class AccessibilityManager {
    constructor() {
        this.highContrastEnabled = false;
        this.announceRegion = document.getElementById('announcements');
        this.focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
        
        this.init();
    }

    /**
     * Initialize accessibility features
     */
    init() {
        this.setupHighContrast();
        this.setupKeyboardNavigation();
        this.setupFocusManagement();
        this.setupAriaLiveRegion();
        this.loadUserPreferences();
        
        // Listen for system preference changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-contrast: high)').addEventListener('change', (e) => {
                if (e.matches && !this.highContrastEnabled) {
                    this.toggleHighContrast();
                }
            });
        }
    }

    /**
     * Setup high contrast mode toggle
     */
    setupHighContrast() {
        const toggleButton = document.getElementById('high-contrast-toggle');
        if (toggleButton) {
            toggleButton.addEventListener('click', () => {
                this.toggleHighContrast();
            });

            // Keyboard support
            toggleButton.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.toggleHighContrast();
                }
            });
        }
    }

    /**
     * Toggle high contrast mode
     */
    toggleHighContrast() {
        this.highContrastEnabled = !this.highContrastEnabled;
        const body = document.body;
        const toggleButton = document.getElementById('high-contrast-toggle');

        if (this.highContrastEnabled) {
            body.classList.add('high-contrast');
            toggleButton?.setAttribute('aria-pressed', 'true');
            this.announce('High contrast mode enabled');
        } else {
            body.classList.remove('high-contrast');
            toggleButton?.setAttribute('aria-pressed', 'false');
            this.announce('High contrast mode disabled');
        }

        // Save preference
        localStorage.setItem('highContrast', this.highContrastEnabled.toString());
    }

    /**
     * Handle forecast keyboard navigation
     */
    handleForecastNavigation(e) {
        const forecastItems = Array.from(document.querySelectorAll('.forecast-item'));
        const currentIndex = forecastItems.indexOf(e.target);
        
        let targetIndex = currentIndex;
        
        switch (e.key) {
            case 'ArrowRight':
                e.preventDefault();
                targetIndex = (currentIndex + 1) % forecastItems.length;
                break;
            case 'ArrowLeft':
                e.preventDefault();
                targetIndex = currentIndex === 0 ? forecastItems.length - 1 : currentIndex - 1;
                break;
            case 'Home':
                e.preventDefault();
                targetIndex = 0;
                break;
            case 'End':
                e.preventDefault();
                targetIndex = forecastItems.length - 1;
                break;
        }
        
        if (targetIndex !== currentIndex) {
            forecastItems[targetIndex].focus();
        }
    }

    /**
     * Setup keyboard navigation
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Alt + C for contrast toggle
            if (e.altKey && e.key.toLowerCase() === 'c') {
                e.preventDefault();
                this.toggleHighContrast();
                return;
            }

            // Escape to close dropdowns/modals
            if (e.key === 'Escape') {
                this.closeDropdowns();
                return;
            }

            // Arrow keys for forecast navigation
            if (e.target.classList.contains('forecast-item')) {
                this.handleForecastNavigation(e);
            }
        });
    }

    /**
     * Close all dropdowns
     */
    closeDropdowns() {
        const suggestions = document.getElementById('search-suggestions');
        if (suggestions && !suggestions.hidden) {
            suggestions.hidden = true;
            document.getElementById('location-input')?.setAttribute('aria-expanded', 'false');
        }
    }

    /**
     * Setup focus management
     */
    setupFocusManagement() {
        // Trap focus in modals/dropdowns when needed
        document.addEventListener('focusin', (e) => {
            // Add focus ring for keyboard users
            if (e.target.matches(this.focusableElements)) {
                e.target.setAttribute('data-keyboard-focus', 'true');
            }
        });

        document.addEventListener('mousedown', (e) => {
            // Remove focus ring for mouse users
            if (e.target.matches(this.focusableElements)) {
                e.target.removeAttribute('data-keyboard-focus');
            }
        });
    }

    /**
     * Setup ARIA live region
     */
    setupAriaLiveRegion() {
        if (!this.announceRegion) {
            this.announceRegion = document.createElement('div');
            this.announceRegion.id = 'announcements';
            this.announceRegion.className = 'visually-hidden';
            this.announceRegion.setAttribute('aria-live', 'polite');
            this.announceRegion.setAttribute('aria-atomic', 'true');
            document.body.appendChild(this.announceRegion);
        }
    }

    /**
     * Announce message to screen readers
     * @param {string} message - Message to announce
     */
    announce(message) {
        if (this.announceRegion) {
            this.announceRegion.textContent = message;
            
            // Clear after announcement
            setTimeout(() => {
                this.announceRegion.textContent = '';
            }, 1000);
        }
    }

    /**
     * Load user preferences
     */
    loadUserPreferences() {
        const savedHighContrast = localStorage.getItem('highContrast');
        if (savedHighContrast === 'true') {
            this.toggleHighContrast();
        }
    }

    /**
     * Focus first focusable element in container
     * @param {HTMLElement} container - Container element
     */
    focusFirst(container) {
        const focusable = container.querySelector(this.focusableElements);
        if (focusable) {
            focusable.focus();
        }
    }

    /**
     * Get all focusable elements in container
     * @param {HTMLElement} container - Container element
     * @returns {NodeList} Focusable elements
     */
    getFocusableElements(container) {
        return container.querySelectorAll(this.focusableElements);
    }
}

// Initialize accessibility manager
window.accessibilityManager = new AccessibilityManager();