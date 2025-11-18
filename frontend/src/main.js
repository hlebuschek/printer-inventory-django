import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrinterInventoryApp from './components/PrinterInventoryApp.vue'
import PrinterListPage from './components/inventory/PrinterListPage.vue'
import PrinterForm from './components/inventory/PrinterForm.vue'
import AmbExportPage from './components/inventory/AmbExportPage.vue'
import WebParserPage from './components/inventory/WebParserPage.vue'
import ContractDeviceListPage from './components/contracts/ContractDeviceListPage.vue'
import MonthListPage from './components/monthly-report/MonthListPage.vue'
import MonthDetailPage from './components/monthly-report/MonthDetailPage.vue'

// Создаем Pinia store
const pinia = createPinia()

// Функция для монтирования приложения
function mountApp(component, elementId) {
  const mountPoint = document.getElementById(elementId)

  if (mountPoint) {
    // Подготавливаем данные от Django
    const propsData = {
      csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
      userId: mountPoint.dataset.userId || null,
      printerId: mountPoint.dataset.printerId || null,
      printerIp: mountPoint.dataset.printerIp || null,
      deviceModelId: mountPoint.dataset.deviceModelId || null,
      permissions: JSON.parse(mountPoint.dataset.permissions || '{}'),
      initialData: JSON.parse(mountPoint.dataset.initialData || '{}'),
      // Для monthly-report
      year: mountPoint.dataset.year ? parseInt(mountPoint.dataset.year) : null,
      month: mountPoint.dataset.month ? parseInt(mountPoint.dataset.month) : null
    }

    // Создаем app с props
    const app = createApp(component, propsData)

    app.use(pinia)

    // Также делаем доступным через provide (для дочерних компонентов)
    app.provide('appConfig', propsData)

    app.mount(`#${elementId}`)

    console.log(`✅ Vue.js ${component.__name || 'app'} mounted successfully on #${elementId}`)
    console.log('Props:', propsData)
  }
}

// Монтируем тестовое приложение (если есть)
mountApp(PrinterInventoryApp, 'printer-inventory-app')

// Монтируем основную страницу списка принтеров (если есть)
mountApp(PrinterListPage, 'printer-list-page')

// Монтируем форму принтера (если есть)
mountApp(PrinterForm, 'printer-form-app')

// Монтируем страницу экспорта AMB (если есть)
mountApp(AmbExportPage, 'amb-export-app')

// Монтируем страницу веб-парсинга (если есть)
mountApp(WebParserPage, 'web-parser-app')

// Монтируем страницу списка устройств по договорам (если есть)
mountApp(ContractDeviceListPage, 'contract-device-list-page')

// Монтируем страницу списка месяцев (monthly_report)
mountApp(MonthListPage, 'month-list-page')

// Монтируем детальную страницу месяца (monthly_report)
mountApp(MonthDetailPage, 'month-detail-page')
