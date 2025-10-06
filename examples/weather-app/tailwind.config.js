/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{html,js}"], // Define paths to your HTML and JS files for TailwindCSS purge
  theme: {
    extend: {
      // Extend default theme styles and add custom configurations
      colors: {
        primary: "#0d6efd",
        secondary: "#6c757d",
        accent: "#ffc107",
      },
    },
  },
  plugins: [],
};