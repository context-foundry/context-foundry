/**
 * Test suite for Weather Configuration
 * Run these tests to verify API configuration setup
 */

class ConfigurationTests {
    constructor() {
        this.testResults = [];
        this.config = new WeatherConfig();
    }

    /**
     * Run all configuration tests
     */
    async runAllTests() {
        console.log('🧪 Starting Weather Configuration Tests...\n');
        
        const tests = [
            this.testConfigInitialization,
            this.testApiKeyValidation,
            this.testUrlGeneration,
            this.testErrorHandling,
            this.testStatusReporting
        ];

        for (const test of tests) {
            try {
                await test.call(this);
            } catch (error) {
                this.addResult(test.name, false, error.message);
            }
        }

        this.displayResults();
        return this.testResults;
    }

    /**
     * Test configuration initialization
     */
    async testConfigInitialization() {
        const testName = 'Configuration Initialization';
        
        // Test initial state
        if (this.config.initialized === false) {
            this.addResult(testName + ' - Initial State', true, 'Config starts uninitialized');
        } else {
            this.addResult(testName + ' - Initial State', false, 'Config should start uninitialized');
        }

        // Test initialization with placeholder key
        const result = await this.config.init();
        
        if (this.config.apiKey === 'your_api_key_here') {
            this.addResult(testName + ' - Placeholder Detection', !result, 'Should fail with placeholder API key');
        } else {
            this.addResult(testName + ' - Real Key', result, result ? 'Initialized successfully' : 'Failed to initialize');
        }
    }

    /**
     * Test API key validation
     */
    async testApiKeyValidation() {
        const testName = 'API Key Validation';
        
        // Test invalid keys
        const invalidKeys = ['', null, undefined, 'short', 'your_api_key_here'];
        
        for (const invalidKey of invalidKeys) {
            this.config.apiKey = invalidKey;
            try {
                this.config.validateApiKey();
                this.addResult(testName + ` - Invalid Key (${invalidKey})`, false, 'Should have thrown error');
            } catch (error) {
                this.addResult(testName + ` - Invalid Key (${invalidKey})`, true, 'Correctly rejected invalid key');
            }
        }

        // Test valid key format (mock)
        this.config.apiKey = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6';
        try {
            this.config.validateApiKey();
            this.addResult(testName + ' - Valid Format', true, 'Accepted valid key format');
        } catch (error) {
            this.addResult(testName + ' - Valid Format', false, error.message);
        }
    }

    /**
     * Test URL generation
     */
    async testUrlGeneration() {
        const testName = 'URL Generation';
        
        // Setup config with mock key
        this.config.apiKey = 'test_key_123456789012345678901234';
        this.config.initialized = true;

        // Test valid city names
        const testCases = [
            { city: 'London', expected: true },
            { city: 'New York', expected: true },
            { city: 'São Paulo', expected: true },
            { city: '', expected: false },
            { city: null, expected: false },
            { city: undefined, expected: false }
        ];

        for (const testCase of testCases) {
            try {
                const url = this.config.getWeatherUrl(testCase.city);
                if (testCase.expected) {
                    const hasCity = url.includes(encodeURIComponent(testCase.city));
                    const hasApiKey = url.includes('appid=test_key_123456789012345678901234');
                    const hasUnits = url.includes('units=metric');
                    
                    const success = hasCity && hasApiKey && hasUnits;
                    this.addResult(
                        testName + ` - ${testCase.city}`, 
                        success, 
                        success ? 'URL generated correctly' : 'URL missing required parameters'
                    );
                } else {
                    this.addResult(testName + ` - ${testCase.city}`, false, 'Should have thrown error');
                }
            } catch (error) {
                if (!testCase.expected) {
                    this.addResult(testName + ` - ${testCase.city}`, true, 'Correctly rejected invalid input');
                } else {
                    this.addResult(testName + ` - ${testCase.city}`, false, error.message);
                }
            }
        }
    }

    /**
     * Test error handling
     */
    async testErrorHandling() {
        const testName = 'Error Handling';
        
        // Test uninitialized config
        const uninitializedConfig = new WeatherConfig();
        try {
            uninitializedConfig.getWeatherUrl('London');
            this.addResult(testName + ' - Uninitialized', false, 'Should throw error when not initialized');
        } catch (error) {
            this.addResult(testName + ' - Uninitialized', true, 'Correctly handles uninitialized state');
        }

        // Test error display
        this.config.showConfigurationError('Test error message');
        const errorElement = document.getElementById('config-error');
        const hasErrorElement = errorElement && errorElement.style.display !== 'none';
        this.addResult(testName + ' - Error Display', hasErrorElement, hasErrorElement ? 'Error message displayed' : 'Error message not shown');

        // Test error hiding
        this.config.hideConfigurationError();
        const errorHidden = errorElement && errorElement.style.display === 'none';
        this.addResult(testName + ' - Error Hiding', errorHidden, errorHidden ? 'Error message hidden' : 'Error message still visible');
    }

    /**
     * Test status reporting
     */
    async testStatusReporting() {
        const testName = 'Status Reporting';
        
        const status = this.config.getStatus();
        const hasRequiredFields = status.hasOwnProperty('initialized') && 
                                 status.hasOwnProperty('hasApiKey') && 
                                 status.hasOwnProperty('baseUrl') && 
                                 status.hasOwnProperty('units');

        this.addResult(testName, hasRequiredFields, hasRequiredFields ? 'Status object complete' : 'Missing status fields');
    }

    /**
     * Add test result
     */
    addResult(testName, passed, message) {
        this.testResults.push({
            name: testName,
            passed,
            message,
            timestamp: new Date().toISOString()
        });

        const emoji = passed ? '✅' : '❌';
        console.log(`${emoji} ${testName}: ${message}`);
    }

    /**
     * Display test summary
     */
    displayResults() {
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        const percentage = Math.round((passed / total) * 100);

        console.log(`\n📊 Test Results: ${passed}/${total} (${percentage}%) passed`);
        
        if (passed === total) {
            console.log('🎉 All tests passed! Configuration is working correctly.');
        } else {
            console.log('⚠️ Some tests failed. Please check the configuration.');
        }

        // Display in UI if possible
        this.displayResultsInUI();
    }

    /**
     * Display test results in UI
     */
    displayResultsInUI() {
        let resultsElement = document.getElementById('test-results');
        if (!resultsElement) {
            resultsElement = document.createElement('div');
            resultsElement.id = 'test-results';
            resultsElement.className = 'test-results';
            document.body.appendChild(resultsElement);
        }

        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;

        resultsElement.innerHTML = `
            <h3>🧪 Configuration Test Results</h3>
            <div class="test-summary">
                <span class="test-score">${passed}/${total} tests passed</span>
                <div class="test-progress">
                    <div class="test-progress-bar" style="width: ${(passed/total)*100}%"></div>
                </div>
            </div>
            <div class="test-details">
                ${this.testResults.map(result => `
                    <div class="test-item ${result.passed ? 'passed' : 'failed'}">
                        <span class="test-icon">${result.passed ? '✅' : '❌'}</span>
                        <span class="test-name">${result.name}</span>
                        <span class="test-message">${result.message}</span>
                    </div>
                `).join('')}
            </div>
        `;

        // Add CSS for test results
        const testStyles = `
            .test-results {
                margin: 20px;
                padding: 20px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            .test-summary {
                margin-bottom: 15px;
            }
            .test-progress {
                width: 100%;
                height: 10px;
                background: #f0f0f0;
                border-radius: 5px;
                overflow: hidden;
                margin-top: 5px;
            }
            .test-progress-bar {
                height: 100%;
                background: #4caf50;
                transition: width 0.3s ease;
            }
            .test-item {
                display: flex;
                align-items: center;
                padding: 5px 0;
                border-bottom: 1px solid #eee;
            }
            .test-icon {
                margin-right: 10px;
            }
            .test-name {
                font-weight: bold;
                margin-right: 10px;
                min-width: 200px;
            }
            .test-message {
                color: #666;
                font-size: 0.9em;
            }
            .test-item.failed .test-message {
                color: #d32f2f;
            }
        `;

        if (!document.getElementById('test-styles')) {
            const styleSheet = document.createElement('style');
            styleSheet.id = 'test-styles';
            styleSheet.textContent = testStyles;
            document.head.appendChild(styleSheet);
        }
    }
}

// Make tests available globally for manual running
window.runConfigTests = async () => {
    const tester = new ConfigurationTests();
    return await tester.runAllTests();
};

// Auto-run tests in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('Development environment detected. Run runConfigTests() to test configuration.');
}