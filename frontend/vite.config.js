import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/mmc/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: false,
        secure: false,
        timeout: 300000,       // 5 min — SQL queries can take time
        proxyTimeout: 300000,  // 5 min proxy-to-flask timeout
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.log('[Vite Proxy Error]', err.message)
          })
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log('[Proxy →]', req.method, req.url)
          })
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log('[Proxy ←]', proxyRes.statusCode, req.url)
          })
        },
      }
    }
  }
})
