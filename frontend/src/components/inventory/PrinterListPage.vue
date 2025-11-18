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
        v-if="permissions.run_inventory || permissions.change_printer"
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

    <!-- Пагинация -->
    <Pagination
      v-if="pagination.totalPages > 1"
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, inject } from 'vue'
import { usePrinterStore } from '../../stores/printerStore'
import { useWebSocket } from '../../composables/useWebSocket'
import { useToast } from '../../composables/useToast'
import PrinterFilters from './PrinterFilters.vue'
import PrinterTable from './PrinterTable.vue'
import Pagination from '../common/Pagination.vue'
import ColumnSelector from './ColumnSelector.vue'
import PrinterModal from './PrinterModal.vue'
import DeleteConfirmModal from './DeleteConfirmModal.vue'

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
  q_ip: initialFilters.q_ip || '',
  q_serial: initialFilters.q_serial || '',
  q_manufacturer: initialFilters.q_manufacturer || '',
  q_device_model: initialFilters.q_device_model || '',
  q_model_text: initialFilters.q_model_text || '',
  q_org: initialFilters.q_org || '',
  q_rule: initialFilters.q_rule || '',
  per_page: initialFilters.per_page || 100,
  page: initialFilters.page || 1
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

const defaultVisibleColumns = allColumns.map(col => col.key)
const visibleColumns = ref(
  JSON.parse(localStorage.getItem('visibleColumns') || JSON.stringify(defaultVisibleColumns))
)

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
  loadData()
}

function changePage(page) {
  filters.page = page
  loadData()
}

function changePerPage(perPage) {
  filters.per_page = perPage
  filters.page = 1
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
  loadData()

  // Listen to WebSocket updates
  window.addEventListener('printer-updated', (event) => {
    const { printerId, status } = event.detail

    if (status === 'SUCCESS') {
      runningPrinters.value.delete(printerId)
      loadData() // Reload to get fresh data
    } else if (status === 'FAILED' || status === 'VALIDATION_ERROR') {
      runningPrinters.value.delete(printerId)
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
  background: #2ecc71;
}

.dot-mac {
  background: #f39c12;
}

.dot-sn {
  background: #3498db;
}

.dot-unknown {
  background: #95a5a6;
}
</style>
