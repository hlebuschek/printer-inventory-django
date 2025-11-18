import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrinterInventoryApp from './components/PrinterInventoryApp.vue'
import PrinterListPage from './components/inventory/PrinterListPage.vue'

// Создаем Pinia store
const pinia = createPinia()

// Функция для монтирования приложения
function mountApp(component, elementId) {
  const mountPoint = document.getElementById(elementId)

  if (mountPoint) {
    const app = createApp(component)

    app.use(pinia)

    // Передаем данные от Django как props
    const propsData = {
      csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
      userId: mountPoint.dataset.userId || null,
      permissions: JSON.parse(mountPoint.dataset.permissions || '{}'),
      initialData: JSON.parse(mountPoint.dataset.initialData || '{}')
    }

    app.provide('appConfig', propsData)

    app.mount(`#${elementId}`)

    console.log(`✅ Vue.js ${component.__name || 'app'} mounted successfully on #${elementId}`)
  }
}

// Монтируем тестовое приложение (если есть)
mountApp(PrinterInventoryApp, 'printer-inventory-app')

// Монтируем основную страницу списка принтеров (если есть)
mountApp(PrinterListPage, 'printer-list-page')
