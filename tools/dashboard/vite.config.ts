import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      // Proxy API requests to CF Daemon
      '/api': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Proxy SSE events endpoint
      '/events': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Proxy status endpoint
      '/status': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Proxy approval endpoints
      '/approve': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      '/deny': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      '/resume-pipeline': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Proxy phase endpoints
      '/phase-prompts': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      '/phase-inject': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      '/phase-acknowledge': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Proxy artifact endpoint
      '/artifact': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Sidekick chat
      '/sidekick-chat': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Pending approvals
      '/pending-approvals': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
      // Auth token
      '/auth-token': {
        target: 'http://localhost:8421',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'markdown-vendor': ['react-markdown', 'rehype-highlight', 'remark-gfm'],
          'state-vendor': ['zustand'],
        },
      },
    },
  },
})
