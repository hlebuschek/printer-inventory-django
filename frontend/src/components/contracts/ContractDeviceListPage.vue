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
            v-for="col in columns"
            :key="col.key"
            class="dropdown-item form-check"
          >
            <input
              v-model="col.visible"
              type="checkbox"
              class="form-check-input me-2"
              :disabled="col.key === 'actions'"
            />
            <span class="form-check-label">{{ col.label }}</span>
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
      @edit="handleEdit"
      @delete="handleDelete"
      @saved="handleDeviceSaved"
      @filter="handleColumnFilter"
      @sort="handleColumnSort"
      @clear-filter="handleClearColumnFilter"
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

    <!-- Фиксированный скроллбар -->
    <FixedScrollbar target-selector=".table-responsive" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'
import ContractDeviceTable from './ContractDeviceTable.vue'
import ContractDeviceModal from './ContractDeviceModal.vue'
import Pagination from '../common/Pagination.vue'
import ToastContainer from '../common/ToastContainer.vue'
import FixedScrollbar from '../common/FixedScrollbar.vue'

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
  choices: {
    org: [],
    city: [],
    address: [],
    room: [],
    mfr: [],
    model: [],
    serial: [],
    status: [],
    service_month: [],
    comment: []
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
const columns = ref([
  { key: 'org', label: 'Организация', visible: true },
  { key: 'city', label: 'Город', visible: true },
  { key: 'address', label: 'Адрес', visible: true },
  { key: 'room', label: '№ кабинета', visible: true },
  { key: 'mfr', label: 'Производитель', visible: true },
  { key: 'model', label: 'Модель оборудования', visible: true },
  { key: 'serial', label: 'Серийный номер', visible: true },
  { key: 'service_month', label: 'Месяц обслуживания', visible: true },
  { key: 'status', label: 'Статус', visible: true },
  { key: 'comment', label: 'Комментарий', visible: true },
  { key: 'actions', label: 'Действия', visible: true }
])

// Computed
const paginationInfo = computed(() => ({
  startIndex: pagination.totalCount > 0 ? (pagination.currentPage - 1) * pagination.perPage + 1 : 0,
  endIndex: Math.min(pagination.currentPage * pagination.perPage, pagination.totalCount)
}))

// Methods
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

async function loadFilterData() {
  try {
    const response = await fetch('/contracts/api/filters/')
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
  loadDevices()
}

function changePage(page) {
  filters.page = page
  loadDevices()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function changePerPage(perPage) {
  filters.per_page = perPage
  filters.page = 1
  loadDevices()
}

function resetColumns() {
  columns.value.forEach(col => {
    col.visible = true
  })
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

function handleColumnFilter(columnKey, value, isMultiple = false) {
  if (isMultiple) {
    filters[columnKey + '__in'] = value
    delete filters[columnKey]
  } else {
    filters[columnKey] = value
    delete filters[columnKey + '__in']
  }
  filters.page = 1
  loadDevices()
}

function handleColumnSort(columnKey, descending) {
  filters.sort = descending ? `-${columnKey}` : columnKey
  loadDevices()
}

function handleClearColumnFilter(columnKey) {
  delete filters[columnKey]
  delete filters[columnKey + '__in']
  filters.page = 1
  loadDevices()
}

// Lifecycle
onMounted(async () => {
  await loadFilterData()
  await loadDevices()
})
</script>

<style scoped>
.contract-device-list-page {
  /* No padding - контент уже в base.html контейнере */
}
</style>
