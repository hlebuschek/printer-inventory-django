<template>
  <div class="month-detail-page">
    <!-- Header with badges -->
    <h1 class="h4 mb-3 d-flex align-items-center gap-2">
      {{ pageTitle }}

      <span v-if="filters.show_anomalies" class="badge bg-warning text-dark">
        ⚠️ Показаны только аномалии
      </span>

      <span v-if="filters.show_unfilled" class="badge bg-info text-dark">
        📝 Показаны только незаполненные
      </span>

      <span v-if="isEditable" class="badge text-bg-success">
        Редактирование открыто до {{ editUntil }}
      </span>
      <span v-else class="badge text-bg-secondary">
        Только чтение
      </span>

      <!-- Auto-sync status -->
      <span v-if="permissions.can_manage_months && !autoSyncEnabled" class="badge text-bg-warning text-dark" title="Автоматическая синхронизация отключена">
        ⚠️ Автосинхронизация выключена
      </span>

      <!-- Override auto-lock badge -->
      <span v-if="permissions.override_auto_lock" class="badge text-bg-primary" title="У вас есть право обхода автоблокировки end-полей">
        Override Lock
      </span>

      <!-- WebSocket connection status -->
      <span v-if="wsConnected" class="badge text-bg-info" title="Подключен к WebSocket. Вы будете видеть изменения других пользователей в реальном времени">
        Live
      </span>
      <span v-else class="badge text-bg-warning text-dark" title="WebSocket отключен. Обновления в реальном времени недоступны">
        Offline
      </span>
    </h1>

    <!-- Edit permissions alert -->
    <div v-if="isEditable" class="alert alert-info py-2 small d-flex align-items-center gap-3">
      <div>
        <strong>Можно редактировать:</strong>
        <span v-if="permissions.edit_counters_start" class="badge text-bg-primary">начало A4/A3</span>
        <span v-if="permissions.edit_counters_end" class="badge text-bg-primary">конец A4/A3</span>
        <em v-if="!permissions.edit_counters_start && !permissions.edit_counters_end">
          нет прав на изменение счётчиков
        </em>
      </div>
      <div class="ms-auto text-muted">Сохранение — по Enter/выходу из поля</div>
    </div>

    <!-- Toolbar -->
    <div class="d-flex gap-2 align-items-center mb-3">
      <!-- Filtered count badge -->
      <div v-if="!loading" class="me-2">
        <span class="badge bg-secondary-subtle text-secondary-emphasis fs-6" title="Количество записей после применения фильтров">
          <i class="bi bi-funnel"></i> {{ pagination.total }} {{ getRecordsLabel(pagination.total) }}
        </span>
      </div>

      <!-- Search form -->
      <div class="row g-2 flex-grow-1">
        <div class="col">
          <input
            v-model="filters.q"
            type="text"
            class="form-control"
            placeholder="Поиск (орг, город, адрес, модель, SN, инв)"
            @input="debouncedSearch"
          />
        </div>
        <div class="col-auto">
          <div class="form-check" style="padding-top: 0.375rem;">
            <input
              id="filter-anomalies"
              v-model="filters.show_anomalies"
              class="form-check-input"
              type="checkbox"
              @change="toggleAnomalies"
            >
            <label class="form-check-label" for="filter-anomalies">
              Только аномалии
            </label>
          </div>
        </div>
        <div class="col-auto">
          <div class="form-check" style="padding-top: 0.375rem;">
            <input
              id="filter-unfilled"
              v-model="filters.show_unfilled"
              class="form-check-input"
              type="checkbox"
              @change="toggleUnfilled"
            >
            <label class="form-check-label" for="filter-unfilled" title="Показать только записи с незаполненными счетчиками (равными 0)">
              Только незаполненные
            </label>
          </div>
        </div>
        <div class="col-auto">
          <button class="btn btn-primary" @click="loadReports">
            Фильтровать
          </button>
        </div>
        <div v-if="permissions.upload_monthly_report" class="col-auto">
          <a class="btn btn-outline-success" href="/monthly-report/upload/">
            Загрузка Excel
          </a>
        </div>
        <div class="col-auto">
          <a class="btn btn-outline-secondary" href="/monthly-report/">
            К списку месяцев
          </a>
        </div>
      </div>

      <!-- Sync button -->
      <button
        v-if="isEditable && permissions.sync_from_inventory"
        type="button"
        class="btn btn-outline-primary"
        :disabled="syncing"
        @click="syncFromInventory"
      >
        Подтянуть из Inventory
      </button>
      <small v-if="syncing" class="text-muted ms-2">Синхронизация...</small>

      <!-- Auto-sync toggle button -->
      <button
        v-if="permissions.can_manage_months"
        type="button"
        :class="['btn', autoSyncEnabled ? 'btn-outline-success' : 'btn-outline-warning']"
        @click="toggleAutoSync"
        :title="autoSyncEnabled ? 'Автосинхронизация включена. Нажмите, чтобы отключить' : 'Автосинхронизация отключена. Нажмите, чтобы включить'"
      >
        <span v-if="autoSyncEnabled">
          ✓ Автосинхронизация
        </span>
        <span v-else>
          ⚠ Автосинхронизация отключена
        </span>
      </button>

      <!-- Columns dropdown -->
      <div class="dropdown">
        <button
          class="btn btn-outline-secondary dropdown-toggle"
          type="button"
          data-bs-toggle="dropdown"
          data-bs-auto-close="outside"
          aria-expanded="false"
        >
          Колонки
        </button>
        <div class="dropdown-menu dropdown-menu-end p-2 columns-menu" style="min-width: 280px;">
          <label
            v-for="(col, idx) in columns"
            :key="col.key"
            class="dropdown-item form-check d-flex align-items-center column-drag-item"
            :class="{ 'column-drag-ghost': dragColumnIndex === idx }"
            draggable="true"
            @dragstart="onColumnDragStart(idx, $event)"
            @dragover.prevent="onColumnDragOver(idx)"
            @drop.prevent="onColumnDragEnd"
            @dragend="onColumnDragEnd"
          >
            <i
              class="bi bi-grip-vertical text-muted me-1 column-drag-handle"
              title="Перетащите, чтобы изменить порядок"
            ></i>
            <input
              v-model="col.visible"
              type="checkbox"
              class="form-check-input me-2 mt-0"
            >
            <span class="form-check-label">{{ col.label }}</span>
            <span class="ms-auto d-flex column-move-buttons">
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
                :disabled="idx >= columns.length - 1"
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

    <!-- Loading state -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <!-- Table -->
    <MonthReportTable
      v-else
      :reports="reports"
      :choices="mergedChoices"
      :permissions="permissions"
      :is-editable="isEditable"
      :current-sort="currentSort"
      :active-filters="activeFilters"
      :column-filter-state="columnFilterState"
      :columns="columns"
      :year="year"
      :month="month"
      @filter="handleFilter"
      @sort="handleSort"
      @clear-filter="handleClearFilter"
      @reload="loadReports"
      @reorder="handleColumnReorder"
    />

    <!-- Pagination -->
    <nav v-if="pagination.total_pages > 1" class="mt-3">
      <ul class="pagination pagination-sm justify-content-center">
        <li class="page-item" :class="{ disabled: !pagination.has_previous }">
          <a class="page-link" href="#" @click.prevent="goToPage(pagination.current_page - 1)">
            Предыдущая
          </a>
        </li>

        <li
          v-for="(page, index) in visiblePages"
          :key="`page-${index}`"
          class="page-item"
          :class="{ active: page === pagination.current_page, disabled: page === '...' }"
        >
          <a v-if="page !== '...'" class="page-link" href="#" @click.prevent="goToPage(page)">
            {{ page }}
          </a>
          <span v-else class="page-link">{{ page }}</span>
        </li>

        <li class="page-item" :class="{ disabled: !pagination.has_next }">
          <a class="page-link" href="#" @click.prevent="goToPage(pagination.current_page + 1)">
            Следующая
          </a>
        </li>
      </ul>

      <div class="text-center text-muted small">
        Показано {{ reports.length }} из {{ pagination.total }} записей
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useToast } from '../../composables/useToast'
import { useUrlFilters } from '../../composables/useUrlFilters'
import MonthReportTable from './MonthReportTable.vue'

const props = defineProps({
  year: {
    type: Number,
    default: null
  },
  month: {
    type: Number,
    default: null
  }
})

const { showToast } = useToast()

// Колонки: порядок + видимость, хранятся в localStorage
const defaultColumns = [
  { key: 'org', label: 'Организация', visible: true },
  { key: 'branch', label: 'Филиал', visible: true },
  { key: 'city', label: 'Город', visible: true },
  { key: 'address', label: 'Адрес', visible: true },
  { key: 'glpi_addr', label: 'Адрес (GLPI)', visible: true },
  { key: 'model', label: 'Модель', visible: true },
  { key: 'serial', label: 'Серийный №', visible: true },
  { key: 'inv', label: 'Инв №', visible: true },
  { key: 'a4bw_s', label: 'A4 ч/б начало', visible: true },
  { key: 'a4bw_e', label: 'A4 ч/б конец', visible: true },
  { key: 'a4c_s', label: 'A4 цв начало', visible: true },
  { key: 'a4c_e', label: 'A4 цв конец', visible: true },
  { key: 'a3bw_s', label: 'A3 ч/б начало', visible: true },
  { key: 'a3bw_e', label: 'A3 ч/б конец', visible: true },
  { key: 'a3c_s', label: 'A3 цв начало', visible: true },
  { key: 'a3c_e', label: 'A3 цв конец', visible: true },
  { key: 'total', label: 'Итого отпечатков', visible: true },
  { key: 'k1', label: 'K1 (%)', visible: false },
  { key: 'k2', label: 'K2 (%)', visible: false }
]

const COLUMNS_STORAGE_KEY = `monthly:columns:v3:${props.year}-${props.month}`
const LEGACY_STORAGE_KEY = `monthly:visibleCols:v2:${props.year}-${props.month}`

function loadColumns() {
  const defaults = () => defaultColumns.map(col => ({ ...col }))
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMNS_STORAGE_KEY))
    if (Array.isArray(saved)) {
      // Формат: массив {key, visible} — хранит и порядок, и видимость
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
      return result
    }
  } catch { /* ignore */ }
  try {
    // Старый формат useColumnVisibility: массив видимых ключей
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY))
    if (Array.isArray(legacy) && legacy.length > 0) {
      const visibleSet = new Set(legacy)
      return defaultColumns.map(col => ({
        ...col,
        // glpi_addr не было в старом формате — показываем по умолчанию
        visible: col.key === 'glpi_addr' ? col.visible : visibleSet.has(col.key)
      }))
    }
  } catch { /* ignore */ }
  return defaults()
}

const columns = ref(loadColumns())

watch(columns, () => {
  const data = columns.value.map(col => ({ key: col.key, visible: col.visible }))
  localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(data))
}, { deep: true })

function resetColumns() {
  columns.value = defaultColumns.map(col => ({ ...col }))
  localStorage.removeItem(COLUMNS_STORAGE_KEY)
  localStorage.removeItem(LEGACY_STORAGE_KEY)
}

// Drag-and-drop порядка колонок в дропдауне
const dragColumnIndex = ref(null)

function onColumnDragStart(idx, event) {
  dragColumnIndex.value = idx
  event.dataTransfer.effectAllowed = 'move'
  // Firefox требует setData, иначе drag не стартует
  event.dataTransfer.setData('text/plain', columns.value[idx].key)
}

function onColumnDragOver(idx) {
  const from = dragColumnIndex.value
  if (from === null || from === idx) return
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
  const moved = columns.value.splice(idx, 1)[0]
  columns.value.splice(to, 0, moved)
}

// Перестановка колонок перетаскиванием заголовков таблицы
function handleColumnReorder(fromKey, toKey) {
  const from = columns.value.findIndex(c => c.key === fromKey)
  const to = columns.value.findIndex(c => c.key === toKey)
  if (from === -1 || to === -1 || from === to) return
  const moved = columns.value.splice(from, 1)[0]
  columns.value.splice(to, 0, moved)
}

const reports = ref([])
const choices = ref({})
const permissions = ref({})
const isEditable = ref(false)
const editUntil = ref(null)
const loading = ref(true)
const syncing = ref(false)
const autoSyncEnabled = ref(true)
const isPublished = ref(false)

// WebSocket для real-time обновлений
let websocket = null
const wsConnected = ref(false)
const wsReconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 5

const pagination = ref({
  total: 0,
  per_page: 100,
  current_page: 1,
  total_pages: 1,
  has_next: false,
  has_previous: false
})

const filters = reactive({
  q: '',
  per_page: 100,
  page: 1,
  sort: 'num',
  show_anomalies: false,
  show_unfilled: false,
  // Column filters (single values)
  org: '',
  branch: '',
  city: '',
  address: '',
  glpi_addr: '',
  model: '',
  serial: '',
  inv: '',
  num: '',
  total: '',
  // Column filters (multiple values)
  org__in: '',
  branch__in: '',
  city__in: '',
  address__in: '',
  glpi_addr__in: '',
  model__in: '',
  serial__in: '',
  inv__in: '',
  num__in: '',
  total__in: ''
})

// URL filters - синхронизация фильтров с URL
const { loadFiltersFromUrl, saveFiltersToUrl } = useUrlFilters(filters, () => {
  // Callback вызывается при popstate (кнопки назад/вперед)
  loadReports() // Загружает reports, choices, permissions и др.
})

// Computed properties
const pageTitle = computed(() => {
  const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ]
  return `${monthNames[props.month - 1]} ${props.year}`
})

const currentSort = computed(() => {
  if (!filters.sort) return { column: null, descending: false }
  const descending = filters.sort.startsWith('-')
  const column = descending ? filters.sort.substring(1) : filters.sort
  return { column, descending }
})

const activeFilters = computed(() => {
  const active = {}
  Object.keys(filters).forEach(key => {
    if (key === 'page' || key === 'per_page' || key === 'sort' || key === 'q' || key.endsWith('__op')) return
    const isSingleFilter = filters[key] && filters[key] !== ''
    const isMultiFilter = key.endsWith('__in') && filters[key] && filters[key] !== ''
    if (isSingleFilter || isMultiFilter) {
      const baseKey = key.replace('__in', '')
      active[baseKey] = true
    }
  })
  return active
})

// Текущее состояние фильтра каждой колонки для ColumnFilter (значение/мультивыбор/оператор)
const columnFilterState = computed(() => {
  const state = {}
  Object.keys(filters).forEach(key => {
    if (key === 'page' || key === 'per_page' || key === 'sort' || key === 'q') return
    if (!filters[key]) return
    const m = key.match(/^(.*?)(__in|__op)?$/)
    const baseKey = m[1]
    const suffix = m[2] || ''
    if (!filterableColumns.includes(baseKey)) return
    if (!state[baseKey]) state[baseKey] = {}
    if (suffix === '__in') state[baseKey].multi = filters[key]
    else if (suffix === '__op') state[baseKey].op = filters[key]
    else state[baseKey].value = filters[key]
  })
  return state
})

const activeFilterCount = computed(() => {
  return Object.keys(activeFilters.value).length
})

// Cross-filtering: динамическое обновление choices на основе текущих фильтров
const filterableColumns = ['org', 'branch', 'city', 'address', 'glpi_addr', 'model', 'serial', 'inv', 'num', 'total']

// Создаем объект с фактическими значениями фильтров (без __in суффиксов)
const actualFilters = computed(() => {
  const result = {}
  Object.keys(filters).forEach(key => {
    const baseKey = key.replace('__in', '')
    if (filterableColumns.includes(baseKey) && filters[key]) {
      result[baseKey] = filters[key]
    }
  })
  return result
})

// Используем composable для кросс-фильтрации
// ВАЖНО: Кросс-фильтрация теперь делается на сервере!
// Сервер учитывает все примененные фильтры (включая show_unfilled)
// и возвращает choices на основе ВСЕХ отфильтрованных записей, а не только текущей страницы.
// Поэтому мы просто используем серверные choices напрямую, без клиентской фильтрации.
const mergedChoices = computed(() => {
  return choices.value
})

const visiblePages = computed(() => {
  const current = pagination.value.current_page
  const total = pagination.value.total_pages
  const delta = 2
  const range = []
  const rangeWithDots = []

  for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) {
    range.push(i)
  }

  if (current - delta > 2) {
    rangeWithDots.push(1, '...')
  } else {
    rangeWithDots.push(1)
  }

  rangeWithDots.push(...range)

  if (current + delta < total - 1) {
    rangeWithDots.push('...', total)
  } else if (total > 1) {
    rangeWithDots.push(total)
  }

  // Возвращаем массив как есть - дубликатов '...' быть не должно,
  // так как они добавляются только в начале (if current - delta > 2) или в конце (if current + delta < total - 1)
  return rangeWithDots
})

// Methods
async function loadReports() {
  // Проверяем что year и month определены
  if (!props.year || !props.month) {
    console.error('Year or month not provided:', props.year, props.month)
    loading.value = false
    return
  }

  loading.value = true
  try {
    const params = new URLSearchParams()
    Object.keys(filters).forEach(key => {
      const value = filters[key]
      // Пропускаем только пустые строки, null и undefined
      // Числа (включая 0) и boolean всегда отправляем
      if (value !== '' && value !== null && value !== undefined) {
        params.append(key, value)
      }
    })

    // ВАЖНО: Всегда отправляем per_page и page даже если они дефолтные
    // Без этого сервер может вернуть все 12000+ записей
    if (!params.has('per_page')) {
      params.set('per_page', filters.per_page)
    }
    if (!params.has('page')) {
      params.set('page', filters.page)
    }

    const response = await fetch(`/monthly-report/api/month/${props.year}/${props.month}/?${params}`)
    const data = await response.json()

    if (data.ok) {
      reports.value = data.reports
      choices.value = data.choices
      permissions.value = data.permissions
      isEditable.value = data.is_editable
      editUntil.value = data.edit_until
      pagination.value = data.pagination
      autoSyncEnabled.value = data.auto_sync_enabled
      isPublished.value = data.is_published
    } else {
      showToast('Ошибка', data.error || 'Не удалось загрузить данные', 'error')
    }
  } catch (error) {
    console.error('Error loading reports:', error)
    showToast('Ошибка', 'Не удалось загрузить данные', 'error')
  } finally {
    loading.value = false
  }
}

let searchTimeout = null
function debouncedSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    filters.page = 1
    saveFiltersToUrl()
    loadReports()
  }, 500)
}

function handleFilter(columnKey, value, isMultiple = false, op = '') {
  if (isMultiple) {
    filters[`${columnKey}__in`] = value
    filters[columnKey] = ''
  } else {
    filters[columnKey] = value
    filters[`${columnKey}__in`] = ''
  }
  filters[`${columnKey}__op`] = op || ''
  filters.page = 1
  saveFiltersToUrl()
  loadReports()
}

function handleSort(columnKey, descending) {
  filters.sort = descending ? `-${columnKey}` : columnKey
  saveFiltersToUrl()
  loadReports()
}

function handleClearFilter(columnKey) {
  filters[columnKey] = ''
  filters[`${columnKey}__in`] = ''
  filters[`${columnKey}__op`] = ''
  filters.page = 1
  saveFiltersToUrl()
  loadReports()
}

function clearAllFilters() {
  filterableColumns.forEach(key => {
    filters[key] = ''
    filters[`${key}__in`] = ''
    filters[`${key}__op`] = ''
  })
  filters.q = ''
  filters.page = 1
  saveFiltersToUrl()
  loadReports()
}

function toggleAnomalies() {
  // Checkbox value is already updated via v-model
  filters.page = 1
  saveFiltersToUrl()
  loadReports()
}

function toggleUnfilled() {
  // Checkbox value is already updated via v-model
  filters.page = 1
  saveFiltersToUrl()
  loadReports()
}

function goToPage(page) {
  if (page < 1 || page > pagination.value.total_pages) return
  filters.page = page
  saveFiltersToUrl()
  loadReports()
}

async function syncFromInventory() {
  if (!confirm('Синхронизировать счётчики из системы опроса?')) return

  syncing.value = true
  try {
    const response = await fetch(`/monthly-report/api/sync/${props.year}/${props.month}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    })
    const data = await response.json()

    if (data.ok) {
      // Формируем детальное сообщение о результатах синхронизации
      const messages = []

      if (data.updated_rows > 0) {
        messages.push(`✅ Обновлено позиций: ${data.updated_rows}`)
      } else {
        messages.push('ℹ️ Нет обновлений')
      }

      if (data.manually_edited_skipped > 0) {
        messages.push(`⚠️ Пропущено (ручное редактирование): ${data.manually_edited_skipped}`)
      }

      if (data.skipped_serials > 0) {
        messages.push(`⏭️ Пропущено (нет данных): ${data.skipped_serials}`)
      }

      if (data.groups_recomputed > 0) {
        messages.push(`🔄 Пересчитано групп: ${data.groups_recomputed}`)
      }

      const message = messages.join('\n')
      showToast('Синхронизация завершена', message, 'success')

      // Обновляем данные только если были изменения
      if (data.updated_rows > 0 || data.groups_recomputed > 0) {
        loadReports()
      }
    } else {
      showToast('Ошибка', data.error || 'Не удалось выполнить синхронизацию', 'error')
    }
  } catch (error) {
    console.error('Error syncing:', error)
    showToast('Ошибка', 'Не удалось выполнить синхронизацию', 'error')
  } finally {
    syncing.value = false
  }
}

async function toggleAutoSync() {
  const newValue = !autoSyncEnabled.value
  const action = newValue ? 'включить' : 'отключить'

  if (!confirm(`Вы уверены, что хотите ${action} автоматическую синхронизацию для этого месяца?`)) {
    return
  }

  try {
    const response = await fetch('/monthly-report/api/toggle-auto-sync/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        year: props.year,
        month: props.month,
        auto_sync_enabled: newValue
      })
    })

    const data = await response.json()

    if (data.success) {
      autoSyncEnabled.value = newValue
      showToast('Успешно', data.message, 'success')
    } else {
      showToast('Ошибка', data.error || 'Не удалось изменить настройку', 'error')
    }
  } catch (error) {
    console.error('Error toggling auto-sync:', error)
    showToast('Ошибка', 'Не удалось изменить настройку', 'error')
  }
}

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function getRecordsLabel(count) {
  const lastDigit = count % 10
  const lastTwoDigits = count % 100

  if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
    return 'записей'
  }

  if (lastDigit === 1) {
    return 'запись'
  }

  if (lastDigit >= 2 && lastDigit <= 4) {
    return 'записи'
  }

  return 'записей'
}

// ============ WebSocket Functions ============

/**
 * Подключение к WebSocket для получения real-time обновлений
 */
function connectWebSocket() {
  // Формируем WebSocket URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const year = props.year
  const month = String(props.month).padStart(2, '0')
  const wsUrl = `${protocol}//${host}/ws/monthly-report/${year}/${month}/`

  try {
    websocket = new WebSocket(wsUrl)

    websocket.onopen = () => {
      wsConnected.value = true
      wsReconnectAttempts.value = 0
    }

    websocket.onmessage = (event) => {
      handleWebSocketMessage(JSON.parse(event.data))
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      wsConnected.value = false
    }

    websocket.onclose = () => {
      wsConnected.value = false

      // Пытаемся переподключиться с экспоненциальной задержкой
      if (wsReconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts.value), 30000)
        wsReconnectAttempts.value++
        setTimeout(connectWebSocket, delay)
      }
    }
  } catch (error) {
    console.error('Failed to create WebSocket:', error)
  }
}

/**
 * Обработка входящих WebSocket сообщений
 */
function handleWebSocketMessage(message) {
  if (message.type === 'counter_update') {
    // Находим запись в таблице
    const reportIndex = reports.value.findIndex(r => r.id === message.report_id)

    if (reportIndex !== -1) {
      const report = reports.value[reportIndex]
      const fieldName = message.field
      const newValue = message.new_value
      const oldValue = message.old_value

      // Обновляем значение в таблице
      if (fieldName in report) {
        // Сохраняем старое значение для проверки конфликта
        const currentValue = report[fieldName]

        // OPTIMISTIC LOCKING: Проверяем конфликт
        // Если текущее значение отличается от старого значения в сообщении,
        // это значит что локально есть несохраненные изменения
        if (currentValue !== oldValue && currentValue !== newValue) {
          console.warn('Conflict detected:', {
            field: fieldName,
            current: currentValue,
            incoming: newValue,
            old: oldValue
          })

          // Показываем предупреждение о конфликте
          const fieldLabels = {
            'a4_bw_start': 'A4 ч/б начало',
            'a4_bw_end': 'A4 ч/б конец',
            'a4_color_start': 'A4 цвет начало',
            'a4_color_end': 'A4 цвет конец',
            'a3_bw_start': 'A3 ч/б начало',
            'a3_bw_end': 'A3 ч/б конец',
            'a3_color_start': 'A3 цвет начало',
            'a3_color_end': 'A3 цвет конец'
          }
          const fieldLabel = fieldLabels[fieldName] || fieldName
          const userName = message.user_full_name || message.user_username

          showToast(
            '⚠️ Конфликт редактирования',
            `${userName} изменил "${fieldLabel}" (${report.equipment_model}, SN: ${report.serial_number})\n` +
            `Ваше значение: ${currentValue}\n` +
            `Значение ${userName}: ${newValue}\n\n` +
            `Пожалуйста, обновите страницу чтобы увидеть актуальные данные.`,
            'warning',
            10000 // 10 секунд
          )

          // НЕ обновляем значение чтобы не потерять локальные изменения
          return
        }

        // Обновляем значение в таблице
        report[fieldName] = newValue

        // Обновляем флаг ручного редактирования, если он есть
        if (message.manual_field && message.manual_field in report) {
          report[message.manual_field] = message.is_manual
        }

        // Помечаем ячейку как обновленную (для визуальной индикации)
        if (!report._wsUpdates) {
          report._wsUpdates = {}
        }
        report._wsUpdates[fieldName] = true

        // Убираем индикацию через 3 секунды
        setTimeout(() => {
          if (report._wsUpdates) {
            delete report._wsUpdates[fieldName]
          }
        }, 3000)

        // ПРИМЕЧАНИЕ: Для end полей total_prints обновится через отдельное сообщение total_prints_update
        // Больше не нужно перезагружать всю таблицу!

        // Показываем уведомление
        const fieldLabels = {
          'a4_bw_start': 'A4 ч/б начало',
          'a4_bw_end': 'A4 ч/б конец',
          'a4_color_start': 'A4 цвет начало',
          'a4_color_end': 'A4 цвет конец',
          'a3_bw_start': 'A3 ч/б начало',
          'a3_bw_end': 'A3 ч/б конец',
          'a3_color_start': 'A3 цвет начало',
          'a3_color_end': 'A3 цвет конец'
        }

        const fieldLabel = fieldLabels[fieldName] || fieldName
        const userName = message.user_full_name || message.user_username

        showToast(
          '🔄 Обновление от другого пользователя',
          `${userName} изменил "${fieldLabel}" для ${report.equipment_model} (SN: ${report.serial_number})\n` +
          `${oldValue} → ${newValue}`,
          'info',
          5000 // 5 секунд
        )
      }
    }
  } else if (message.type === 'total_prints_update') {
    // Обработка обновления total_prints после пересчета группы
    // Это позволяет точечно обновить таблицу без полной перезагрузки
    const reportIndex = reports.value.findIndex(r => r.id === message.report_id)

    if (reportIndex !== -1) {
      const report = reports.value[reportIndex]

      // Обновляем total_prints и аномалию
      report.total_prints = message.total_prints
      report.is_anomaly = message.is_anomaly

      // Обновляем anomaly_info если есть
      if (message.anomaly_info) {
        report.anomaly_average = message.anomaly_info.average
        report.anomaly_difference = message.anomaly_info.difference
        report.anomaly_percentage = message.anomaly_info.percentage
        report.anomaly_months_count = message.anomaly_info.months_count
      }

      // Помечаем ячейку total_prints как обновленную (для визуальной анимации)
      if (!report._wsUpdates) {
        report._wsUpdates = {}
      }
      report._wsUpdates['total_prints'] = true

      // Убираем анимацию через 2 секунды
      setTimeout(() => {
        if (report._wsUpdates) {
          delete report._wsUpdates['total_prints']
        }
      }, 2000)

    }
  } else if (message.type === 'inventory_sync_update') {
    // Обработка автоматического обновления из inventory (опрос принтера)
    // Обновляет счётчики только для полей где НЕ было ручного редактирования
    const reportIndex = reports.value.findIndex(r => r.id === message.report_id)

    if (reportIndex !== -1) {
      const report = reports.value[reportIndex]

      // Обновляем счётчики
      report.a4_bw_end = message.a4_bw_end
      report.a4_color_end = message.a4_color_end
      report.a3_bw_end = message.a3_bw_end
      report.a3_color_end = message.a3_color_end
      report.total_prints = message.total_prints
      report.is_anomaly = message.is_anomaly
      report.anomaly_info = message.anomaly_info
      report.inventory_last_ok = message.inventory_last_ok

      // Помечаем обновлённые ячейки для визуальной анимации
      if (!report._wsUpdates) {
        report._wsUpdates = {}
      }
      report._wsUpdates['a4_bw_end'] = true
      report._wsUpdates['a4_color_end'] = true
      report._wsUpdates['a3_bw_end'] = true
      report._wsUpdates['a3_color_end'] = true
      report._wsUpdates['total_prints'] = true

      // Убираем анимацию через 3 секунды
      setTimeout(() => {
        if (report._wsUpdates) {
          delete report._wsUpdates['a4_bw_end']
          delete report._wsUpdates['a4_color_end']
          delete report._wsUpdates['a3_bw_end']
          delete report._wsUpdates['a3_color_end']
          delete report._wsUpdates['total_prints']
        }
      }, 3000)
    }
  }
}

/**
 * Отключение от WebSocket
 */
function disconnectWebSocket() {
  if (websocket) {
    websocket.close()
    websocket = null
    wsConnected.value = false
  }
}

// ============ Lifecycle Hooks ============

onMounted(() => {
  // Загружаем фильтры из URL перед загрузкой данных
  loadFiltersFromUrl()
  loadReports()
  connectWebSocket()
})

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style scoped>
.month-detail-page {
  padding: 2rem 0 5rem 0; /* Увеличенные отступы для видимости заголовка и пагинации */
}

/* ===== Columns menu styling ===== */
.columns-menu {
  min-width: 350px !important;
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
