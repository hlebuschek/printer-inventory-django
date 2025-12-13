import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { printersApi } from '@/utils/api'

export const usePrinterStore = defineStore('printers', () => {
  // State
  const printers = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Фильтры
  const filters = ref({
    q_ip: '',
    q_serial: '',
    q_manufacturer: '',
    q_device_model: '',
    q_model_text: '',
    q_org: '',
    q_rule: ''
  })

  // Пагинация
  const pagination = ref({
    page: 1,
    perPage: 50,
    totalCount: 0,
    totalPages: 0
  })

  // Видимые колонки (из localStorage)
  const visibleColumns = ref([
    'col-organization', 'col-ip_address', 'col-serial_number', 'col-mac_address',
    'col-device_model', 'col-bw_a4', 'col-color_a4', 'col-bw_a3', 'col-color_a3',
    'col-total', 'col-drums', 'col-toners', 'col-fuser_kit', 'col-transfer_kit',
    'col-waste_toner', 'col-timestamp', 'col-match_rule', 'col-actions'
  ])

  // Полирующие принтеры (показываем спиннер)
  const pollingPrinters = ref(new Set())

  // Свежеобновленные принтеры (показываем зеленую подсветку)
  const freshPrinters = ref(new Set())

  // Getters
  const filteredPrinters = computed(() => {
    return printers.value
  })

  const isPrinterPolling = computed(() => (id) => {
    return pollingPrinters.value.has(id)
  })

  const isPrinterFresh = computed(() => (id) => {
    return freshPrinters.value.has(id)
  })

  // Actions
  async function fetchPrinters(params = {}) {
    loading.value = true
    error.value = null

    try {
      const response = await printersApi.getAll({
        ...filters.value,
        page: pagination.value.page,
        per_page: pagination.value.perPage,
        ...params
      })

      // Предполагаем что API возвращает { printers: [], pagination: {} }
      if (Array.isArray(response)) {
        printers.value = response
      } else {
        printers.value = response.printers || response.data || []
        if (response.pagination) {
          pagination.value = { ...pagination.value, ...response.pagination }
        }
      }

      return printers.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch printers:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function runInventory(printerId) {
    pollingPrinters.value.add(printerId)

    try {
      await printersApi.runInventory(printerId)
    } catch (err) {
      console.error('Failed to run inventory:', err)
      pollingPrinters.value.delete(printerId)
      throw err
    }
  }

  async function runInventoryAll() {
    try {
      await printersApi.runInventoryAll()
      // Добавляем все принтеры в список опрашиваемых
      printers.value.forEach(p => pollingPrinters.value.add(p.printer?.id || p.id))
    } catch (err) {
      console.error('Failed to run inventory for all:', err)
      throw err
    }
  }

  function updatePrinterFromWebSocket(data) {
    const printerId = data.printer_id

    // Убираем из опрашиваемых
    pollingPrinters.value.delete(printerId)

    // Добавляем в свежие
    freshPrinters.value.add(printerId)
    setTimeout(() => {
      freshPrinters.value.delete(printerId)
    }, 5000)

    // Обновляем данные принтера
    const index = printers.value.findIndex(p =>
      (p.printer?.id || p.id) === printerId
    )

    if (index !== -1) {
      const printer = printers.value[index]

      // Обновляем поля счетчиков
      const fields = ['bw_a4', 'color_a4', 'bw_a3', 'color_a3', 'total']
      fields.forEach(field => {
        if (data[field] !== undefined) {
          printer[field] = data[field]
        }
      })

      // Обновляем расходники
      const supplies = [
        'toner_black', 'toner_cyan', 'toner_magenta', 'toner_yellow',
        'drum_black', 'drum_cyan', 'drum_magenta', 'drum_yellow',
        'fuser_kit', 'transfer_kit', 'waste_toner'
      ]
      supplies.forEach(field => {
        if (data[field] !== undefined) {
          printer[field] = data[field]
        }
      })

      // Обновляем метку времени
      if (data.timestamp) {
        printer.last_date = data.timestamp
      }

      // Обновляем match_rule
      if (data.match_rule && printer.printer) {
        printer.printer.last_match_rule = data.match_rule
      }

      // Заменяем принтер в массиве
      printers.value[index] = { ...printer }
    }
  }

  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
  }

  function setPage(page) {
    pagination.value.page = page
  }

  function setPerPage(perPage) {
    pagination.value.perPage = perPage
    pagination.value.page = 1 // Сбрасываем на первую страницу
  }

  function loadVisibleColumns() {
    const stored = localStorage.getItem('visibleColumns')
    if (stored) {
      try {
        visibleColumns.value = JSON.parse(stored)
      } catch (e) {
        console.error('Failed to parse visible columns:', e)
      }
    }
  }

  function saveVisibleColumns() {
    localStorage.setItem('visibleColumns', JSON.stringify(visibleColumns.value))
  }

  function toggleColumn(columnId) {
    const index = visibleColumns.value.indexOf(columnId)
    if (index > -1) {
      visibleColumns.value.splice(index, 1)
    } else {
      visibleColumns.value.push(columnId)
    }
    saveVisibleColumns()
  }

  function isColumnVisible(columnId) {
    return visibleColumns.value.includes(columnId)
  }

  // Инициализация
  loadVisibleColumns()

  return {
    // State
    printers,
    loading,
    error,
    filters,
    pagination,
    visibleColumns,
    pollingPrinters,
    freshPrinters,

    // Getters
    filteredPrinters,
    isPrinterPolling,
    isPrinterFresh,

    // Actions
    fetchPrinters,
    runInventory,
    runInventoryAll,
    updatePrinterFromWebSocket,
    setFilters,
    setPage,
    setPerPage,
    toggleColumn,
    isColumnVisible,
    saveVisibleColumns
  }
})
