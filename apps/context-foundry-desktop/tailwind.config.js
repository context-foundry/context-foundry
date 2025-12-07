/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Context Foundry brand colors
        cf: {
          primary: '#6366f1',
          secondary: '#8b5cf6',
          accent: '#06b6d4',
          background: '#0f172a',
          surface: '#1e293b',
          border: '#334155',
          text: '#f1f5f9',
          muted: '#94a3b8',
        },
        // Status colors
        status: {
          running: '#22c55e',
          pending: '#eab308',
          failed: '#ef4444',
          succeeded: '#22c55e',
          cancelled: '#6b7280',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
    },
  },
  plugins: [],
}
