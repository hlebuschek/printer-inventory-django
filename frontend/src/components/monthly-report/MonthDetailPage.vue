<template>
  <div class="month-detail-page">
    <!-- Header -->
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h1 class="h4 mb-1">{{ pageTitle }}</h1>
        <div v-if="isEditable" class="text-success small">
          <i class="bi bi-unlock"></i> Редактирование открыто до {{ editUntil }}
        </div>
        <div v-else class="text-muted small">
          <i class="bi bi-lock"></i> Редактирование закрыто
        </div>
      </div>

      <div class="d-flex gap-2">
        <!-- Sync button -->
        <button
          v-if="permissions.sync_from_inventory"
          class="btn btn-primary btn-sm"
          :disabled="syncing"
          @click="syncFromInventory"
        >
          <i class="bi bi-arrow-repeat"></i> Синхронизация
        </button>

        <!-- Export button -->
        <a
          :href="`/monthly-report/${year}/${month}/export-excel/`"
          class="btn btn-success btn-sm"
        >
          <i class="bi bi-download"></i> Excel
        </a>

        <!-- Back button -->
        <a href="/monthly-report/" class="btn btn-outline-secondary btn-sm">
          <i class="bi bi-arrow-left"></i> Назад
        </a>
      </div>
    </div>

    <!-- Search and filters -->
    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-2">
          <!-- Search -->
          <div class="col-md-4">
            <input
              v-model="filters.q"
              type="text"
              class="form-control form-control-sm"
              placeholder="Поиск по всем полям..."
              @input="debouncedSearch"
            />
          </div>

          <!-- Per page -->
          <div class="col-md-2">
            <select v-model="filters.per_page" class="form-select form-select-sm" @change="loadReports">
              <option value="100">100 записей</option>
              <option value="200">200 записей</option>
              <option value="500">500 записей</option>
              <option value="1000">1000 записей</option>
              <option value="all">Все</option>
            </select>
          </div>

          <!-- Active filters count -->
          <div class="col-md-6 d-flex align-items-center justify-content-end">
            <span v-if="activeFilterCount > 0" class="badge bg-primary me-2">
              Активных фильтров: {{ activeFilterCount }}
            </span>
            <button
              v-if="activeFilterCount > 0"
              class="btn btn-outline-secondary btn-sm"
              @click="clearAllFilters"
            >
              <i class="bi bi-x-circle"></i> Очистить фильтры
            </button>
          </div>
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
      :choices="choices"
      :permissions="permissions"
      :is-editable="isEditable"
      :current-sort="currentSort"
      :active-filters="activeFilters"
      @filter="handleFilter"
      @sort="handleSort"
      @clear-filter="handleClearFilter"
      @saved="loadReports"
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
          v-for="page in visiblePages"
          :key="page"
          class="page-item"
          :class="{ active: page === pagination.current_page }"
        >
          <a class="page-link" href="#" @click.prevent="goToPage(page)">
            {{ page }}
          </a>
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
import { ref, computed, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'
import MonthReportTable from './MonthReportTable.vue'

const props = defineProps({
  year: {
    type: Number,
    required: true
  },
  month: {
    type: Number,
    required: true
  }
})

const { showToast } = useToast()

const reports = ref([])
const choices = ref({})
const permissions = ref({})
const isEditable = ref(false)
const editUntil = ref(null)
const loading = ref(true)
const syncing = ref(false)

const pagination = ref({
  total: 0,
  per_page: 100,
  current_page: 1,
  total_pages: 1,
  has_next: false,
  has_previous: false
})

const filters = ref({
  q: '',
  per_page: '100',
  page: 1,
  sort: 'num',
  // Column filters
  org__in: '',
  branch__in: '',
  city__in: '',
  address__in: '',
  model__in: '',
  serial__in: '',
  inv__in: '',
  num__in: ''
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
  if (!filters.value.sort) return { column: null, descending: false }
  const descending = filters.value.sort.startsWith('-')
  const column = descending ? filters.value.sort.substring(1) : filters.value.sort
  return { column, descending }
})

const activeFilters = computed(() => {
  const active = {}
  Object.keys(filters.value).forEach(key => {
    if (key === 'page' || key === 'per_page' || key === 'sort' || key === 'q') return
    const isSingleFilter = filters.value[key] && filters.value[key] !== ''
    const isMultiFilter = key.endsWith('__in') && filters.value[key] && filters.value[key] !== ''
    if (isSingleFilter || isMultiFilter) {
      const baseKey = key.replace('__in', '')
      active[baseKey] = true
    }
  })
  return active
})

const activeFilterCount = computed(() => {
  return Object.keys(activeFilters.value).length
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

  return rangeWithDots.filter(p => p !== '...' || rangeWithDots.indexOf(p) === rangeWithDots.lastIndexOf(p))
})

// Methods
async function loadReports() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    Object.keys(filters.value).forEach(key => {
      if (filters.value[key]) {
        params.append(key, filters.value[key])
      }
    })

    const response = await fetch(`/monthly-report/api/month/${props.year}/${props.month}/?${params}`)
    const data = await response.json()

    if (data.ok) {
      reports.value = data.reports
      choices.value = data.choices
      permissions.value = data.permissions
      isEditable.value = data.is_editable
      editUntil.value = data.edit_until
      pagination.value = data.pagination
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
    filters.value.page = 1
    loadReports()
  }, 500)
}

function handleFilter(columnKey, value, isMultiple = false) {
  const filterKey = isMultiple ? `${columnKey}__in` : columnKey
  filters.value[filterKey] = value
  filters.value.page = 1
  loadReports()
}

function handleSort(columnKey, descending) {
  filters.value.sort = descending ? `-${columnKey}` : columnKey
  loadReports()
}

function handleClearFilter(columnKey) {
  filters.value[columnKey] = ''
  filters.value[`${columnKey}__in`] = ''
  filters.value.page = 1
  loadReports()
}

function clearAllFilters() {
  filters.value.org__in = ''
  filters.value.branch__in = ''
  filters.value.city__in = ''
  filters.value.address__in = ''
  filters.value.model__in = ''
  filters.value.serial__in = ''
  filters.value.inv__in = ''
  filters.value.num__in = ''
  filters.value.q = ''
  filters.value.page = 1
  loadReports()
}

function goToPage(page) {
  if (page < 1 || page > pagination.value.total_pages) return
  filters.value.page = page
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
      showToast('Успех', 'Синхронизация завершена', 'success')
      loadReports()
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

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.month-detail-page {
  padding: 0;
}
</style>
