/**
 * Header component for the Weather App.
 * Displays the title of the application.
 * 
 * @returns {HTMLElement} - The DOM element for the header.
 */
function Header() {
  const header = document.createElement("header");
  header.className = "bg-blue-500 text-white text-center py-4 shadow-lg";

  const title = document.createElement("h1");
  title.className = "text-3xl font-bold";
  title.innerText = "Weather App";

  header.appendChild(title);
  return header;
}

export default Header;