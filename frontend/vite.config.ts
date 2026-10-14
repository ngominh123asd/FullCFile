import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Manual chunks for better caching & parallel loading
        manualChunks: {
          // React core - rarely changes
          'react-vendor': ['react', 'react-dom'],
          // Router
          'router-vendor': ['react-router-dom'],
          // State & Data fetching
          'state-vendor': ['@tanstack/react-query', 'zustand'],
          // UI & Icons
          'ui-vendor': ['lucide-react', 'framer-motion', 'clsx', 'tailwind-merge'],
          // Form components
          'form-vendor': ['react-dropzone'],
          // Radix UI primitives (heavy, load on demand)
          'radix-vendor': [
            '@radix-ui/react-slot',
            '@radix-ui/react-dialog',
            '@radix-ui/react-tabs',
            '@radix-ui/react-progress',
            '@radix-ui/react-select',
            '@radix-ui/react-tooltip',
          ],
        },
        // Chunk file naming
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
    // Target modern browsers for smaller bundles
    target: 'esnext',
    // Minify with optimal settings
    minify: 'esbuild',
    // CSS minification
    cssMinify: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://localhost:${loadEnv(mode, '..', '').OCR_BACKEND_PORT || '8000'}`,
        changeOrigin: true,
      },
    },
  },
  // Pre-bundle dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'zustand',
      '@tanstack/react-query',
      'lucide-react',
    ],
  },
}))
