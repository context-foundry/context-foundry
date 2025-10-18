// Test functionality related to local storage for recent searches

// Test save to local storage
function testSaveSearch() {
    // Clear localStorage before testing
    localStorage.clear();
  
    saveSearchToLocal('New York');
    let searches = JSON.parse(localStorage.getItem('recentSearches'));
    console.assert(searches.length === 1 && searches[0] === 'New York', 'Test Failed: New York was not saved correctly');
}

// Test load recent searches
function testLoadRecentSearches() {
    localStorage.setItem('recentSearches', JSON.stringify(['Los Angeles', 'Chicago']));
    document.body.innerHTML = '<ul id="recent-searches"></ul>'; // Mock DOM

    loadRecentSearches();
    const items = document.querySelectorAll('#recent-searches li');
    console.assert(items.length === 2, 'Test Failed: Recent searches were not loaded correctly');
    console.assert(items[0].textContent === 'Los Angeles', 'Test Failed: First item was not Los Angeles');
    console.assert(items[1].textContent === 'Chicago', 'Test Failed: Second item was not Chicago');
}

// Running tests
testSaveSearch();
testLoadRecentSearches();