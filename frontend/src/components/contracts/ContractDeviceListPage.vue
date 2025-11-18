<template>
  <div class="contract-device-list-page">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h2 class="mb-0">Устройства в договоре</h2>
      <button
        v-if="permissions.add_contractdevice"
        class="btn btn-success"
        @click="openAddModal"
      >
        <i class="bi bi-plus-circle me-1"></i>
        Добавить устройство
      </button>
    </div>

    <!-- Фильтры -->
    <ContractDeviceFilters
      v-model:filters="filters"
      :filter-data="filterData"
      @apply="applyFilters"
      @reset="resetFilters"
      @export-excel="exportExcel"
    />

    <!-- Информация о записях -->
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div class="text-muted">
        Показано {{ pagination.startIndex }}-{{ pagination.endIndex }} из {{ pagination.totalCount }} устройств
      </div>
      <div class="text-muted">
        Страница {{ pagination.currentPage }} из {{ pagination.totalPages }}
      </div>
    </div>

    <!-- Таблица устройств -->
    <ContractDeviceTable
      :devices="devices"
      :loading="isLoading"
      @edit="handleEdit"
      @delete="handleDelete"
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'
import ContractDeviceFilters from './ContractDeviceFilters.vue'
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
  statuses: []
})
const isLoading = ref(false)
const showModal = ref(false)
const selectedDevice = ref(null)

const filters = reactive({
  organization: [],
  city: [],
  address: '',
  room: '',
  manufacturer: [],
  model: '',
  serial: '',
  status: [],
  service_month: '',
  comment: '',
  page: 1,
  per_page: 50
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
      // Handle array filters (multi-select)
      if (Array.isArray(value) && value.length > 0) {
        params.append(key, value.join('||'))
      }
      // Handle string filters
      else if (value && value !== '' && !Array.isArray(value)) {
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

function applyFilters() {
  filters.page = 1
  loadDevices()
}

function resetFilters() {
  Object.keys(filters).forEach(key => {
    if (key !== 'per_page' && key !== 'page') {
      // Reset array filters to empty array
      if (Array.isArray(filters[key])) {
        filters[key] = []
      } else {
        filters[key] = ''
      }
    }
  })
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

// Lifecycle
onMounted(async () => {
  await loadFilterData()
  await loadDevices()
})
</script>

<style scoped>
.contract-device-list-page {
  padding: 20px;
}
</style>
