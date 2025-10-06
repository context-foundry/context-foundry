// Functionality to handle search and local storage for recent searches

// Save the recent searches to local storage
function saveSearchToLocal(search) {
    let searches = JSON.parse(localStorage.getItem('recentSearches')) || [];
    if (!searches.includes(search)) {
        if (searches.length >= 5) {
            searches.shift(); // Remove the oldest search to limit to 5
        }
        searches.push(search);
        localStorage.setItem('recentSearches', JSON.stringify(searches));
    }
}

// Load recent searches from local storage
function loadRecentSearches() {
    const searches = JSON.parse(localStorage.getItem('recentSearches')) || [];
    const searchList = document.getElementById('recent-searches');
    searchList.innerHTML = ''; // Clear the list first
    searches.forEach(search => {
        const listItem = document.createElement('li');
        listItem.textContent = search;
        listItem.onclick = () => {
            document.getElementById('search-input').value = search;
            performSearch(search); // Assuming there's a function to perform the search
        };
        searchList.appendChild(listItem);
    });
}

// Execute the search and save it to local storage
function performSearch(search) {
    // Perform the weather search logic here (API call, etc.)
    saveSearchToLocal(search);
}

// Event listener for the input form
document.getElementById('search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const searchValue = document.getElementById('search-input').value.trim();
    if (searchValue) {
        performSearch(searchValue);
        loadRecentSearches(); // Reload the recent searches
    }
});

// Load recent searches when the page is first loaded
window.onload = loadRecentSearches;