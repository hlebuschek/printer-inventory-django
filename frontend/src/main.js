import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrinterInventoryApp from './components/PrinterInventoryApp.vue'

// Создаем Pinia store
const pinia = createPinia()

// Монтируем Vue приложение только если есть контейнер
const mountPoint = document.getElementById('printer-inventory-app')

if (mountPoint) {
  const app = createApp(PrinterInventoryApp)

  app.use(pinia)

  // Передаем данные от Django как props
  const propsData = {
    csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
    userId: mountPoint.dataset.userId || null,
    permissions: JSON.parse(mountPoint.dataset.permissions || '{}'),
    initialData: JSON.parse(mountPoint.dataset.initialData || '{}')
  }

  app.provide('appConfig', propsData)

  app.mount('#printer-inventory-app')

  console.log('✅ Vue.js Printer Inventory mounted successfully')
}
