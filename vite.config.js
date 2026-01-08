import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  // Используем разные base для dev и production
  const base = command === 'build' ? '/static/' : '/'

  return {
    // Корневая директория для Vite (где находится index.html)
    root: 'frontend',

    plugins: [vue()],

    base,

    build: {
      // Генерируем файлы в static/dist/
      outDir: resolve(__dirname, 'static/dist'),
      emptyOutDir: true,

      manifest: true,

      rollupOptions: {
        // Entry points для разных страниц
        input: {
          main: resolve(__dirname, 'frontend/src/main.js'),
        },

        output: {
          // Структура выходных файлов
          entryFileNames: 'js/[name].[hash].js',
          chunkFileNames: 'js/[name].[hash].js',
          assetFileNames: (assetInfo) => {
            if (assetInfo.name.endsWith('.css')) {
              return 'css/[name].[hash][extname]'
            }
            return 'assets/[name].[hash][extname]'
          }
        }
      }
    },

    server: {
      // Для dev режима - прокси на Django
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,

      // Прокси API запросы на Django
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:5000',
          ws: true,
        }
      }
    },

    resolve: {
      alias: {
        '@': resolve(__dirname, 'frontend/src'),
      }
    }
  }
})
