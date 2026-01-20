<template>
  <div class="printer-list-page">
    <!-- Фильтры -->
    <PrinterFilters
      v-model:filters="filters"
      :manufacturers="manufacturers"
      :device-models="deviceModels"
      :organizations="organizations"
      :permissions="permissions"
      @apply="applyFilters"
      @reset="resetFilters"
      @export-excel="exportExcel"
      @export-amb="exportAmb"
      @open-column-selector="showColumnSelector = true"
    />

    <!-- Кнопки действий -->
    <div class="mb-3">
      <a
        v-if="permissions.add_printer"
        :href="urls.addPrinter"
        class="btn btn-success me-2"
      >
        <i class="bi bi-plus-circle me-1"></i> Добавить принтер
      </a>

      <button
        v-if="permissions.can_poll_all_printers"
        class="btn btn-primary"
        :disabled="isRunningAll"
        @click="runInventoryAll"
      >
        <span
          v-if="isRunningAll"
          class="spinner-border spinner-border-sm me-2"
        ></span>
        <span>
          <i class="bi bi-arrow-repeat me-1"></i>
          {{ isRunningAll ? 'Опрос…' : 'Запустить опрос всех' }}
        </span>
      </button>
    </div>

    <!-- Информация о записях -->
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div class="text-muted">
        Показано {{ pagination.startIndex }}-{{ pagination.endIndex }} из {{ pagination.totalCount }} принтеров
      </div>
      <div class="text-muted">
        Страница {{ pagination.currentPage }} из {{ pagination.totalPages }}
      </div>
    </div>

    <!-- Легенда -->
    <div class="mb-2 small text-muted">
      <span class="match-dot dot-sn-mac"></span> Серийник+MAC&nbsp;&nbsp;
      <span class="match-dot dot-mac"></span> Только MAC&nbsp;&nbsp;
      <span class="match-dot dot-sn"></span> Только серийник
    </div>

    <!-- Таблица принтеров -->
    <PrinterTable
      :printers="printers"
      :visible-columns="visibleColumns"
      :permissions="permissions"
      :running-printers="runningPrinters"
      @edit="openEditModal"
      @delete="openDeleteModal"
      @history="openHistoryModal"
      @run-poll="runInventory"
      @email="handleEmail"
      @web-parser="handleWebParser"
    />

    <!-- Пагинация - показываем всегда, селектор per-page полезен даже на одной странице -->
    <Pagination
      :current-page="pagination.currentPage"
      :total-pages="pagination.totalPages"
      :per-page="filters.per_page"
      :per-page-options="perPageOptions"
      @page-change="changePage"
      @per-page-change="changePerPage"
    />

    <!-- Модальные окна -->
    <ColumnSelector
      v-model:show="showColumnSelector"
      v-model:visible-columns="visibleColumns"
      :all-columns="allColumns"
    />

    <PrinterModal
      v-model:show="showPrinterModal"
      :printer-id="selectedPrinterId"
      :mode="modalMode"
      :organizations="organizations"
      :permissions="permissions"
      @updated="handlePrinterUpdated"
    />

    <DeleteConfirmModal
      v-model:show="showDeleteModal"
      :printer="selectedPrinter"
      @confirm="confirmDelete"
    />

    <!-- Toast уведомления -->
    <ToastContainer />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, inject } from 'vue'
import { usePrinterStore } from '../../stores/printerStore'
import { useWebSocket } from '../../composables/useWebSocket'
import { useToast } from '../../composables/useToast'
import { useUrlFilters } from '../../composables/useUrlFilters'
import PrinterFilters from './PrinterFilters.vue'
import PrinterTable from './PrinterTable.vue'
import Pagination from '../common/Pagination.vue'
import ColumnSelector from './ColumnSelector.vue'
import PrinterModal from './PrinterModal.vue'
import DeleteConfirmModal from './DeleteConfirmModal.vue'
import ToastContainer from '../common/ToastContainer.vue'

// Inject app config
const appConfig = inject('appConfig', {})

// Store and composables
const printerStore = usePrinterStore()
const { showToast } = useToast()
const { connected: wsConnected } = useWebSocket()

// Props from Django
const permissions = reactive(appConfig.permissions || {})
const initialFilters = reactive(appConfig.initialData?.filters || {})

// URLs
const urls = {
  addPrinter: '/inventory/add/',
  exportExcel: '/inventory/export/',
  exportAmb: '/inventory/export-amb/'
}

// State
const manufacturers = ref([])
const deviceModels = ref([])
const organizations = ref([])
const printers = ref([])
const runningPrinters = ref(new Set())
const isRunningAll = ref(false)

// Pagination
const pagination = reactive({
  currentPage: 1,
  totalPages: 1,
  totalCount: 0,
  startIndex: 0,
  endIndex: 0
})

const perPageOptions = [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]

// Filters
const filters = reactive({
  q_ip: '',
  q_serial: '',
  q_manufacturer: '',
  q_device_model: '',
  q_org: '',
  q_rule: '',
  per_page: 100,
  page: 1
})

// URL filters - синхронизация фильтров с URL
const { loadFiltersFromUrl, saveFiltersToUrl, clearFiltersFromUrl } = useUrlFilters(filters, () => {
  // Callback вызывается при popstate (кнопки назад/вперед)
  loadData()
})

// Columns
const allColumns = [
  { key: 'organization', label: 'Организация', disabled: false },
  { key: 'ip_address', label: 'IP-адрес', disabled: true },
  { key: 'serial_number', label: 'Серийный №', disabled: true },
  { key: 'mac_address', label: 'MAC-адрес', disabled: false },
  { key: 'device_model', label: 'Модель', disabled: false },
  { key: 'bw_a4', label: 'ЧБ A4', disabled: false },
  { key: 'color_a4', label: 'Цвет A4', disabled: false },
  { key: 'bw_a3', label: 'ЧБ A3', disabled: false },
  { key: 'color_a3', label: 'Цвет A3', disabled: false },
  { key: 'total', label: 'Всего', disabled: false },
  { key: 'drums', label: 'Барабаны (K/C/M/Y)', disabled: false },
  { key: 'toners', label: 'Тонеры (K/C/M/Y)', disabled: false },
  { key: 'fuser_kit', label: 'Fuser Kit', disabled: false },
  { key: 'transfer_kit', label: 'Transfer Kit', disabled: false },
  { key: 'waste_toner', label: 'Waste Toner', disabled: false },
  { key: 'timestamp', label: 'Дата опроса', disabled: false },
  { key: 'match_rule', label: 'Правило', disabled: false },
  { key: 'actions', label: 'Действия', disabled: true }
]

// По умолчанию показываем ВСЕ столбцы - пользователь сам решит что скрывать
const defaultVisibleColumns = allColumns.map(col => col.key)

// Инициализация видимых столбцов с валидацией
const getInitialColumns = () => {
  try {
    const stored = localStorage.getItem('visibleColumns')
    if (stored) {
      const parsed = JSON.parse(stored)
      // Проверяем что массив не пустой и содержит только валидные столбцы
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Получаем список всех доступных ключей столбцов
        const validKeys = allColumns.map(col => col.key)
        // Фильтруем только валидные столбцы
        const validColumns = parsed.filter(key => validKeys.includes(key))

        // Если после фильтрации остались столбцы, используем их
        if (validColumns.length > 0) {
          return validColumns
        }
      }
    }
  } catch (e) {
    console.warn('Failed to parse visibleColumns from localStorage:', e)
  }
  // Иначе используем столбцы по умолчанию
  return defaultVisibleColumns
}

const visibleColumns = ref(getInitialColumns())

// Modals
const showColumnSelector = ref(false)
const showPrinterModal = ref(false)
const showDeleteModal = ref(false)
const selectedPrinterId = ref(null)
const selectedPrinter = ref(null)
const modalMode = ref('edit') // 'edit' or 'history'

// Methods
async function loadData() {
  try {
    const response = await fetch(`/inventory/api/printers/?${new URLSearchParams(filters)}`)
    const data = await response.json()

    printers.value = data.printers || []
    manufacturers.value = data.manufacturers || []
    deviceModels.value = data.device_models || []
    organizations.value = data.organizations || []

    // Update pagination
    pagination.currentPage = data.page || 1
    pagination.totalPages = data.total_pages || 1
    pagination.totalCount = data.total_count || 0
    pagination.startIndex = data.start_index || 0
    pagination.endIndex = data.end_index || 0
  } catch (error) {
    console.error('Error loading printers:', error)
    showToast('Ошибка', 'Не удалось загрузить данные принтеров', 'error')
  }
}

function applyFilters() {
  filters.page = 1 // Reset to first page
  saveFiltersToUrl()
  loadData()
}

function resetFilters() {
  Object.keys(filters).forEach(key => {
    if (key === 'per_page') {
      filters[key] = 100
    } else if (key === 'page') {
      filters[key] = 1
    } else {
      filters[key] = ''
    }
  })
  clearFiltersFromUrl()
  loadData()
}

function changePage(page) {
  filters.page = page
  saveFiltersToUrl()
  loadData()
}

function changePerPage(perPage) {
  filters.per_page = perPage
  filters.page = 1
  saveFiltersToUrl()
  loadData()
}

function exportExcel() {
  window.location.href = `${urls.exportExcel}?${new URLSearchParams(filters)}`
}

function exportAmb() {
  // Redirect to AMB export page
  window.location.href = urls.exportAmb
}

async function runInventory(printerId) {
  runningPrinters.value.add(printerId)

  try {
    const response = await fetch(`/inventory/${printerId}/run/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (!data.success) {
      showToast('Ошибка', `Не удалось запустить опрос: ${data.error}`, 'error')
      runningPrinters.value.delete(printerId)
    }
  } catch (error) {
    console.error('Error running inventory:', error)
    showToast('Ошибка', 'Не удалось запустить опрос', 'error')
    runningPrinters.value.delete(printerId)
  }
}

async function runInventoryAll() {
  isRunningAll.value = true

  try {
    const response = await fetch('/inventory/run_all/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (data.success) {
      showToast('Успех', 'Запущен опрос всех принтеров', 'success')
    } else {
      showToast('Ошибка', `Не удалось запустить опрос: ${data.error}`, 'error')
      isRunningAll.value = false
    }
  } catch (error) {
    console.error('Error running inventory all:', error)
    showToast('Ошибка', 'Не удалось запустить опрос всех', 'error')
    isRunningAll.value = false
  }
}

function openEditModal(printerId) {
  selectedPrinterId.value = printerId
  modalMode.value = 'edit'
  showPrinterModal.value = true
}

function openHistoryModal(printerId) {
  selectedPrinterId.value = printerId
  modalMode.value = 'history'
  showPrinterModal.value = true
}

function openDeleteModal(printer) {
  selectedPrinter.value = printer
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!selectedPrinter.value) return

  try {
    const response = await fetch(`/inventory/${selectedPrinter.value.id}/delete/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      }
    })

    const data = await response.json()

    if (data.success) {
      showToast('Успех', 'Принтер удалён', 'success')
      loadData()
    } else {
      showToast('Ошибка', 'Не удалось удалить принтер', 'error')
    }
  } catch (error) {
    console.error('Error deleting printer:', error)
    showToast('Ошибка', 'Не удалось удалить принтер', 'error')
  }

  showDeleteModal.value = false
  selectedPrinter.value = null
}

function handlePrinterUpdated() {
  loadData()
}

async function handleEmail(printer) {
  if (!printer.serial_number) {
    showToast('Ошибка', 'У принтера отсутствует серийный номер', 'error')
    return
  }

  try {
    const response = await fetch(`/contracts/api/lookup-by-serial/?serial=${encodeURIComponent(printer.serial_number)}`)
    const data = await response.json()

    if (!data.ok || !data.found) {
      showToast('Ошибка', `Устройство с серийным номером ${printer.serial_number} не найдено в договорах`, 'error')
      return
    }

    window.location.href = `/contracts/${data.device.id}/email/`
  } catch (error) {
    console.error('Error checking device:', error)
    showToast('Ошибка', 'Не удалось проверить устройство', 'error')
  }
}

function handleWebParser(printerId) {
  window.location.href = `/inventory/${printerId}/web-parser/`
}

// Utility functions
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

// Lifecycle
onMounted(() => {
  // Загружаем фильтры из URL перед загрузкой данных
  loadFiltersFromUrl()
  loadData()

  // Listen to WebSocket updates
  window.addEventListener('printer-updated', (event) => {
    const { printerId, status, data } = event.detail

    // Убираем спиннер
    runningPrinters.value.delete(printerId)

    if (status === 'SUCCESS' && data) {
      // Динамически обновляем данные принтера в таблице
      const printerIndex = printers.value.findIndex(p => p.id === printerId)

      if (printerIndex !== -1) {
        const oldPrinter = printers.value[printerIndex]
        const oldCounters = oldPrinter.counters || {}

        // Создаем обновленный объект counters
        const updatedCounters = {
          ...oldCounters,
          bw_a3: data.bw_a3 ?? oldCounters.bw_a3,
          bw_a4: data.bw_a4 ?? oldCounters.bw_a4,
          color_a3: data.color_a3 ?? oldCounters.color_a3,
          color_a4: data.color_a4 ?? oldCounters.color_a4,
          total: data.total ?? oldCounters.total,
          drum_black: data.drum_black ?? oldCounters.drum_black,
          drum_cyan: data.drum_cyan ?? oldCounters.drum_cyan,
          drum_magenta: data.drum_magenta ?? oldCounters.drum_magenta,
          drum_yellow: data.drum_yellow ?? oldCounters.drum_yellow,
          toner_black: data.toner_black ?? oldCounters.toner_black,
          toner_cyan: data.toner_cyan ?? oldCounters.toner_cyan,
          toner_magenta: data.toner_magenta ?? oldCounters.toner_magenta,
          toner_yellow: data.toner_yellow ?? oldCounters.toner_yellow,
          fuser_kit: data.fuser_kit ?? oldCounters.fuser_kit,
          transfer_kit: data.transfer_kit ?? oldCounters.transfer_kit,
          waste_toner: data.waste_toner ?? oldCounters.waste_toner,
        }

        // Форматируем дату из timestamp (миллисекунды)
        let formattedDate = oldPrinter.last_date
        if (data.timestamp) {
          const date = new Date(data.timestamp)
          // Форматируем как YYYY-MM-DD HH:MM:SS
          const year = date.getFullYear()
          const month = String(date.getMonth() + 1).padStart(2, '0')
          const day = String(date.getDate()).padStart(2, '0')
          const hours = String(date.getHours()).padStart(2, '0')
          const minutes = String(date.getMinutes()).padStart(2, '0')
          const seconds = String(date.getSeconds()).padStart(2, '0')
          formattedDate = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
        }

        // Создаем обновленный объект принтера (для Vue реактивности)
        const updatedPrinter = {
          ...oldPrinter,
          mac_address: data.mac_address ?? oldPrinter.mac_address,  // Обновляем MAC
          counters: updatedCounters,
          last_date: formattedDate,
          last_match_rule: data.match_rule ?? oldPrinter.last_match_rule,  // Обновляем правило (круглышок)
        }

        // Заменяем объект целиком для корректной реактивности Vue 3
        printers.value[printerIndex] = updatedPrinter
      }
    }
  })

  window.addEventListener('inventory-all-complete', () => {
    isRunningAll.value = false
  })
})

onUnmounted(() => {
  // Clean up event listeners if needed
})
</script>

<style scoped>
.match-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  vertical-align: middle;
}

.dot-sn-mac {
  background: var(--pi-status-fresh, #2ecc71);
}

.dot-mac {
  background: var(--pi-status-warning, #f39c12);
}

.dot-sn {
  background: var(--pi-status-info, #3498db);
}

.dot-unknown {
  background: var(--pi-status-unknown, #95a5a6);
}
</style>
