import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  base: '/static/dist/',
  build: {
    outDir: 'src/ccconfigmanager/static/dist',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 8920,
    proxy: {
      '/api': 'http://127.0.0.1:8900',
      '/static': 'http://127.0.0.1:8900',
    },
  },
})
