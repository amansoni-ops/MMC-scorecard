import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env vars (VITE_BASE_PATH, VITE_API_BASE) so they're actually
  // usable here -- defineConfig's plain object form (the old version)
  // never read process.env at all, which is why VITE_BASE_PATH has been
  // silently ignored on every build despite being passed correctly on
  // the command line. loadEnv + the function form of defineConfig is
  // required to actually wire env vars into the config.
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    // THE FIX: base path for all asset references Vite generates
    // (<script src>, <link href>, dynamic imports, etc.). Falls back to
    // '/' for local dev (npm run dev with no env var set), and uses
    // VITE_BASE_PATH (e.g. '/mmc/') for production builds where the app
    // is served from a subpath behind nginx.
    base: env.VITE_BASE_PATH || '/',
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
  }
})



// import { defineConfig } from 'vite'
// import react from '@vitejs/plugin-react'

// export default defineConfig({
//   plugins: [react()],
//   server: {
//     port: 5173,
//     proxy: {
//       '/api': {
//         target: 'http://127.0.0.1:5000',
//         changeOrigin: false,
//         secure: false,
//         timeout: 300000,       // 5 min — SQL queries can take time
//         proxyTimeout: 300000,  // 5 min proxy-to-flask timeout
//         configure: (proxy) => {
//           proxy.on('error', (err) => {
//             console.log('[Vite Proxy Error]', err.message)
//           })
//           proxy.on('proxyReq', (proxyReq, req) => {
//             console.log('[Proxy →]', req.method, req.url)
//           })
//           proxy.on('proxyRes', (proxyRes, req) => {
//             console.log('[Proxy ←]', proxyRes.statusCode, req.url)
//           })
//         },
//       }
//     }
//   }
// })
