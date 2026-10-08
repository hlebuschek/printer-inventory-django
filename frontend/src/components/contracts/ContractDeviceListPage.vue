<template>
  <div class="contract-device-list-page">
    <h1 class="h4 mb-3">Устройства в договоре</h1>

    <!-- Поиск и кнопки -->
    <div class="d-flex gap-2 align-items-center mb-3">
      <form class="row g-2 flex-grow-1" @submit.prevent="applySearch">
        <div class="col">
          <input
            v-model="searchQuery"
            type="text"
            class="form-control"
            placeholder="Поиск (SN, адрес, модель, комментарий)"
          />
        </div>
        <div class="col-auto">
          <button type="submit" class="btn btn-primary">Фильтровать</button>
        </div>
        <div v-if="permissions.export_contracts" class="col-auto">
          <button type="button" class="btn btn-outline-success" @click="exportExcel">
            Экспорт в Excel
          </button>
        </div>
        <div v-if="permissions.add_contractdevice" class="col-auto">
          <button type="button" class="btn btn-outline-secondary" @click="openAddModal">
            Добавить
          </button>
        </div>
        <div v-if="permissions.import_contracts" class="col-auto">
          <a href="/contracts/import/" class="btn btn-outline-primary">
            <i class="bi bi-upload"></i> Импорт из Excel
          </a>
        </div>
      </form>

      <!-- Переключатель колонок -->
      <div class="dropdown">
        <button
          class="btn btn-outline-secondary dropdown-toggle"
          type="button"
          data-bs-toggle="dropdown"
          aria-expanded="false"
        >
          Колонки
        </button>
        <div class="dropdown-menu dropdown-menu-end p-2" style="min-width: 260px">
          <label
            v-for="(col, idx) in columns"
            :key="col.key"
            class="dropdown-item form-check d-flex align-items-center column-drag-item"
            :class="{ 'column-drag-ghost': dragColumnIndex === idx }"
            :draggable="col.key !== 'actions'"
            @dragstart="onColumnDragStart(idx, $event)"
            @dragover.prevent="onColumnDragOver(idx)"
            @drop.prevent="onColumnDragEnd"
            @dragend="onColumnDragEnd"
          >
            <i
              v-if="col.key !== 'actions'"
              class="bi bi-grip-vertical text-muted me-1 column-drag-handle"
              title="Перетащите, чтобы изменить порядок"
            ></i>
            <i v-else class="bi bi-grip-vertical me-1 invisible"></i>
            <input
              v-model="col.visible"
              type="checkbox"
              class="form-check-input me-2 mt-0"
              :disabled="col.key === 'actions'"
            />
            <span class="form-check-label">{{ col.label }}</span>
            <span v-if="col.key !== 'actions'" class="ms-auto d-flex column-move-buttons">
              <button
                type="button"
                class="btn btn-link btn-sm p-0 px-1 text-muted"
                title="Выше"
                :disabled="idx === 0"
                @click.stop.prevent="moveColumn(idx, -1)"
              >
                <i class="bi bi-chevron-up"></i>
              </button>
              <button
                type="button"
                class="btn btn-link btn-sm p-0 px-1 text-muted"
                title="Ниже"
                :disabled="columns[idx + 1]?.key === 'actions' || idx >= columns.length - 1"
                @click.stop.prevent="moveColumn(idx, 1)"
              >
                <i class="bi bi-chevron-down"></i>
              </button>
            </span>
          </label>
          <div class="dropdown-divider"></div>
          <button class="btn btn-sm btn-outline-secondary w-100" @click="resetColumns">
            Сброс
          </button>
        </div>
      </div>
    </div>

    <!-- Таблица устройств -->
    <ContractDeviceTable
      :devices="devices"
      :loading="isLoading"
      :filter-data="filterData"
      :columns="columns"
      :permissions="permissions"
      :current-sort="currentSort"
      :active-filters="activeFilters"
      :column-filter-state="columnFilterState"
      :start-index="pagination.startIndex"
      @edit="handleEdit"
      @delete="handleDelete"
      @saved="handleDeviceSaved"
      @issue-created="handleIssueCreated"
      @filter="handleColumnFilter"
      @sort="handleColumnSort"
      @clear-filter="handleClearColumnFilter"
      @reorder="handleColumnReorder"
    />

    <!-- Пагинация -->
    <Pagination
      :current-page="pagination.currentPage"
      :total-pages="pagination.totalPages"
      :per-page="filters.per_page"
      :per-page-options="perPageOptions"
      @page-change="changePage"
      @per-page-change="changePerPage"
    />

    <!-- Модальное окно создания/редактирования -->
    <ContractDeviceModal
      v-model:show="showModal"
      :device="selectedDevice"
      :filter-data="filterData"
      @saved="handleDeviceSaved"
    />

    <!-- Toast уведомления -->
    <ToastContainer />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'
import { useUrlFilters } from '../../composables/useUrlFilters'
import ContractDeviceTable from './ContractDeviceTable.vue'
import ContractDeviceModal from './ContractDeviceModal.vue'
import Pagination from '../common/Pagination.vue'
import ToastContainer from '../common/ToastContainer.vue'

// Props
const props = defineProps({
  permissions: {
    type: Object,
    default: () => ({})
  }
})

// Toast notifications
const { showToast } = useToast()

// State
const devices = ref([])
const filterData = ref({
  organizations: [],
  cities: [],
  manufacturers: [],
  statuses: [],
  providers: [],
  choices: {
    org: [],
    city: [],
    address: [],
    room: [],
    mfr: [],
    model: [],
    serial: [],
    status: [],
    provider: [],
    service_month: [],
    comment: [],
    okdesk_active: [],
    okdesk_overdue: [],
    glpi: [],
    glpi_state: []
  }
})
const isLoading = ref(false)
const showModal = ref(false)
const selectedDevice = ref(null)
const searchQuery = ref('')

const filters = reactive({
  q: '',
  page: 1,
  per_page: 50,
  sort: ''
})

// URL filters - синхронизация фильтров с URL
const { loadFiltersFromUrl, saveFiltersToUrl, clearFiltersFromUrl } = useUrlFilters(filters, async () => {
  // Callback вызывается при popstate (кнопки назад/вперед)
  await loadFilterData()
  await loadDevices()
})

const pagination = reactive({
  totalCount: 0,
  totalPages: 0,
  currentPage: 1,
  perPage: 50,
  startIndex: 0,
  endIndex: 0
})

const perPageOptions = [25, 50, 100, 200, 500, 1000]

// Columns configuration
const COLUMNS_STORAGE_KEY = 'contracts_columns_visibility'

const defaultColumns = [
  { key: 'org', label: 'Организация', visible: true },
  { key: 'city', label: 'Город', visible: true },
  { key: 'address', label: 'Адрес', visible: true },
  { key: 'glpi_location', label: 'Адрес (GLPI)', visible: true },
  { key: 'room', label: '№ кабинета', visible: true },
  { key: 'mfr', label: 'Производитель', visible: true },
  { key: 'model', label: 'Модель оборудования', visible: true },
  { key: 'serial', label: 'Серийный номер', visible: true },
  { key: 'service_month', label: 'Месяц обслуживания', visible: true },
  { key: 'initial_counter', label: 'Счётчик при приёмке', visible: true },
  { key: 'status', label: 'Статус', visible: true },
  { key: 'provider', label: 'Подрядчик', visible: true },
  { key: 'comment', label: 'Комментарий', visible: true },
  { key: 'okdesk_author', label: 'Автор заявки', visible: true },
  { key: 'okdesk_active', label: 'Активные заявки', visible: true },
  { key: 'okdesk_overdue', label: 'Просроченные', visible: true },
  { key: 'glpi', label: 'GLPI', visible: true },
  { key: 'glpi_state', label: 'Состояние в GLPI', visible: true },
  { key: 'actions', label: 'Действия', visible: true }
]

function loadColumnVisibility() {
  const defaults = () => defaultColumns.map(col => ({ ...col }))
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMNS_STORAGE_KEY))
    if (Array.isArray(saved)) {
      // Новый формат: массив {key, visible} — хранит и порядок, и видимость
      const defaultsByKey = Object.fromEntries(defaultColumns.map(c => [c.key, c]))
      const result = []
      for (const item of saved) {
        const def = defaultsByKey[item.key]
        if (def) {
          result.push({ ...def, visible: !!item.visible })
          delete defaultsByKey[item.key]
        }
      }
      // Колонки, добавленные после сохранения, вставляем на их позицию по умолчанию
      defaultColumns.forEach((def, idx) => {
        if (defaultsByKey[def.key]) {
          result.splice(Math.min(idx, result.length), 0, { ...def })
        }
      })
      // "Действия" всегда последняя
      const actionsIdx = result.findIndex(c => c.key === 'actions')
      if (actionsIdx !== -1 && actionsIdx !== result.length - 1) {
        result.push(result.splice(actionsIdx, 1)[0])
      }
      return result
    }
    if (saved && typeof saved === 'object') {
      // Старый формат: map {key: visible}
      return defaultColumns.map(col => ({
        ...col,
        visible: col.key in saved ? saved[col.key] : col.visible
      }))
    }
  } catch { /* ignore */ }
  return defaults()
}

function saveColumnVisibility() {
  const data = columns.value.map(col => ({ key: col.key, visible: col.visible }))
  localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(data))
}

const columns = ref(loadColumnVisibility())

// Сохраняем видимость и порядок столбцов при изменении
watch(columns, saveColumnVisibility, { deep: true })

// Drag-and-drop порядка колонок в дропдауне
const dragColumnIndex = ref(null)

function onColumnDragStart(idx, event) {
  if (columns.value[idx].key === 'actions') {
    event.preventDefault()
    return
  }
  dragColumnIndex.value = idx
  event.dataTransfer.effectAllowed = 'move'
  // Firefox требует setData, иначе drag не стартует
  event.dataTransfer.setData('text/plain', columns.value[idx].key)
}

function onColumnDragOver(idx) {
  const from = dragColumnIndex.value
  if (from === null || from === idx) return
  if (columns.value[idx].key === 'actions') return
  const moved = columns.value.splice(from, 1)[0]
  columns.value.splice(idx, 0, moved)
  dragColumnIndex.value = idx
}

function onColumnDragEnd() {
  dragColumnIndex.value = null
}

// Перемещение колонки стрелками в дропдауне
function moveColumn(idx, delta) {
  const to = idx + delta
  if (to < 0 || to >= columns.value.length) return
  if (columns.value[idx].key === 'actions' || columns.value[to].key === 'actions') return
  const moved = columns.value.splice(idx, 1)[0]
  columns.value.splice(to, 0, moved)
}

// Перестановка колонок перетаскиванием заголовков таблицы
function handleColumnReorder(fromKey, toKey) {
  const from = columns.value.findIndex(c => c.key === fromKey)
  const to = columns.value.findIndex(c => c.key === toKey)
  if (from === -1 || to === -1 || from === to) return
  if (columns.value[to].key === 'actions') return
  const moved = columns.value.splice(from, 1)[0]
  columns.value.splice(to, 0, moved)
}

// Computed
const paginationInfo = computed(() => ({
  startIndex: pagination.totalCount > 0 ? (pagination.currentPage - 1) * pagination.perPage : 0,
  endIndex: Math.min(pagination.currentPage * pagination.perPage, pagination.totalCount)
}))

const currentSort = computed(() => {
  if (!filters.sort) return { column: null, descending: false }

  const descending = filters.sort.startsWith('-')
  const column = descending ? filters.sort.substring(1) : filters.sort

  // Map backend keys back to frontend keys
  const reverseKeyMap = {
    'organization': 'org',
    'manufacturer': 'mfr'
  }

  const frontendColumn = reverseKeyMap[column] || column

  return { column: frontendColumn, descending }
})

const activeFilters = computed(() => {
  const active = {}

  // Map backend keys to frontend keys
  const reverseKeyMap = {
    'organization': 'org',
    'manufacturer': 'mfr'
  }

  Object.keys(filters).forEach(key => {
    if (key === 'page' || key === 'per_page' || key === 'sort' || key === 'q' || key.endsWith('__op')) {
      return
    }

    // Check if filter is active (either single or multiple)
    const isSingleFilter = key in filters && filters[key] && filters[key] !== ''
    const isMultiFilter = key.endsWith('__in') && filters[key] && filters[key] !== ''

    if (isSingleFilter || isMultiFilter) {
      // Remove __in suffix if present
      const baseKey = key.replace('__in', '')
      // Map to frontend key
      const frontendKey = reverseKeyMap[baseKey] || baseKey
      active[frontendKey] = true
    }
  })

  return active
})

// Текущее состояние фильтра каждой колонки для ColumnFilter (значение/мультивыбор/оператор)
const columnFilterState = computed(() => {
  const reverseKeyMap = {
    'organization': 'org',
    'manufacturer': 'mfr'
  }
  const state = {}
  Object.keys(filters).forEach(key => {
    if (key === 'page' || key === 'per_page' || key === 'sort' || key === 'q') return
    if (!filters[key]) return
    const m = key.match(/^(.*?)(__in|__op)?$/)
    const baseKey = m[1]
    const suffix = m[2] || ''
    const frontendKey = reverseKeyMap[baseKey] || baseKey
    if (!state[frontendKey]) state[frontendKey] = {}
    if (suffix === '__in') state[frontendKey].multi = filters[key]
    else if (suffix === '__op') state[frontendKey].op = filters[key]
    else state[frontendKey].value = filters[key]
  })
  return state
})

// Methods
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

async function loadFilterData() {
  try {
    // Передаем текущие фильтры для кросс-фильтрации
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== '' && key !== 'page' && key !== 'per_page' && key !== 'sort' && key !== 'q') {
        params.append(key, value)
      }
    })

    const url = params.toString()
      ? `/contracts/api/filters/?${params.toString()}`
      : '/contracts/api/filters/'

    const response = await fetch(url)
    const data = await response.json()
    filterData.value = data
  } catch (error) {
    console.error('Error loading filter data:', error)
    showToast('Ошибка', 'Не удалось загрузить данные для фильтров', 'error')
  }
}

async function loadDevices() {
  isLoading.value = true

  try {
    // Формируем query параметры
    const params = new URLSearchParams()

    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== '') {
        params.append(key, value)
      }
    })

    const response = await fetch(`/contracts/api/devices/?${params.toString()}`)
    const data = await response.json()

    devices.value = data.devices || []

    // Обновляем пагинацию
    pagination.totalCount = data.pagination.total_count
    pagination.totalPages = data.pagination.total_pages
    pagination.currentPage = data.pagination.current_page
    pagination.perPage = data.pagination.per_page
    pagination.startIndex = paginationInfo.value.startIndex
    pagination.endIndex = paginationInfo.value.endIndex

  } catch (error) {
    console.error('Error loading devices:', error)
    showToast('Ошибка', 'Не удалось загрузить список устройств', 'error')
  } finally {
    isLoading.value = false
  }
}

function applySearch() {
  filters.q = searchQuery.value
  filters.page = 1
  saveFiltersToUrl()
  loadDevices()
}

function changePage(page) {
  filters.page = page
  saveFiltersToUrl()
  loadDevices()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function changePerPage(perPage) {
  filters.per_page = perPage
  filters.page = 1
  saveFiltersToUrl()
  loadDevices()
}

function resetColumns() {
  columns.value = defaultColumns.map(col => ({ ...col }))
  localStorage.removeItem(COLUMNS_STORAGE_KEY)
}

function openAddModal() {
  selectedDevice.value = null
  showModal.value = true
}

function handleEdit(device) {
  selectedDevice.value = device
  showModal.value = true
}

function handleDeviceSaved() {
  loadDevices()
}

async function handleIssueCreated() {
  // Обновляем фильтры (новый автор появится в выпадайке) и таблицу
  await loadFilterData()
  await loadDevices()
}

async function handleDelete(device) {
  if (!confirm(`Удалить устройство ${device.model} (${device.serial_number})?`)) {
    return
  }

  try {
    const response = await fetch(`/contracts/api/${device.id}/delete/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    })

    const data = await response.json()

    if (data.ok) {
      showToast('Успех', 'Устройство удалено', 'success')
      loadDevices()
    } else {
      showToast('Ошибка', 'Не удалось удалить устройство', 'error')
    }
  } catch (error) {
    console.error('Error deleting device:', error)
    showToast('Ошибка', 'Не удалось удалить устройство', 'error')
  }
}

function exportExcel() {
  // Экспорт в Excel
  window.location.href = '/contracts/export/'
}

async function handleColumnFilter(columnKey, value, isMultiple = false, op = '') {
  // Map frontend column keys to backend filter keys
  const keyMap = {
    'org': 'organization',
    'mfr': 'manufacturer'
  }

  const backendKey = keyMap[columnKey] || columnKey

  if (isMultiple) {
    filters[backendKey + '__in'] = value
    delete filters[backendKey]
  } else {
    filters[backendKey] = value
    delete filters[backendKey + '__in']
  }
  if (op) {
    filters[backendKey + '__op'] = op
  } else {
    delete filters[backendKey + '__op']
  }
  filters.page = 1
  saveFiltersToUrl()

  // Reload filter data for cross-filtering
  await loadFilterData()
  await loadDevices()
}

function handleColumnSort(columnKey, descending) {
  // Map frontend column keys to backend filter keys
  const keyMap = {
    'org': 'organization',
    'mfr': 'manufacturer'
  }

  const backendKey = keyMap[columnKey] || columnKey
  filters.sort = descending ? `-${backendKey}` : backendKey
  filters.page = 1
  saveFiltersToUrl()
  loadDevices()
}

async function handleClearColumnFilter(columnKey) {
  // Map frontend column keys to backend filter keys
  const keyMap = {
    'org': 'organization',
    'mfr': 'manufacturer'
  }

  const backendKey = keyMap[columnKey] || columnKey
  delete filters[backendKey]
  delete filters[backendKey + '__in']
  delete filters[backendKey + '__op']
  filters.page = 1
  saveFiltersToUrl()

  // Reload filter data for cross-filtering
  await loadFilterData()
  await loadDevices()
}

// Lifecycle
onMounted(async () => {
  // Загружаем фильтры из URL перед загрузкой данных
  loadFiltersFromUrl()
  // Синхронизируем поле поиска с фильтром из URL
  searchQuery.value = filters.q
  await loadFilterData()
  await loadDevices()
})
</script>

<style scoped>
.contract-device-list-page {
  /* Отступ снизу, чтобы floating scrollbar не закрывал пагинацию */
  padding-bottom: 30px;
}

.column-drag-item {
  cursor: default;
}

.column-drag-handle {
  cursor: grab;
}

.column-drag-ghost {
  opacity: 0.4;
  background-color: var(--bs-secondary-bg);
}
</style>
