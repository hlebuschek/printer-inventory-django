<template>
  <div class="contract-device-table">
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
      <p class="mt-2">Загрузка устройств...</p>
    </div>

    <div v-else-if="!devices.length" class="alert alert-info">
      <i class="bi bi-info-circle me-2"></i>
      Устройства не найдены. Попробуйте изменить параметры фильтрации.
    </div>

    <div v-else class="table-responsive table-responsive-fixed">
      <table ref="tableRef" class="table table-hover table-sm table-fixed table-resizable">
        <thead class="table-light">
          <tr>
            <th style="width: 3%">#</th>
            <th style="width: 12%">Организация</th>
            <th style="width: 8%">Город</th>
            <th style="width: 15%">Адрес</th>
            <th style="width: 5%">Каб.</th>
            <th style="width: 10%">Производитель</th>
            <th style="width: 10%">Модель</th>
            <th style="width: 10%">S/N</th>
            <th style="width: 8%">Статус</th>
            <th style="width: 7%">Месяц</th>
            <th style="width: 12%">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(device, index) in devices"
            :key="device.id"
            :class="{ editing: editingId === device.id }"
          >
            <td>{{ index + 1 }}</td>

            <!-- Организация -->
            <td>
              <select
                v-if="editingId === device.id"
                v-model="editForm.organization_id"
                class="form-select form-select-sm"
              >
                <option
                  v-for="org in filterData.organizations"
                  :key="org.id"
                  :value="org.id"
                >
                  {{ org.name }}
                </option>
              </select>
              <span v-else>{{ device.organization }}</span>
            </td>

            <!-- Город -->
            <td>
              <select
                v-if="editingId === device.id"
                v-model="editForm.city_id"
                class="form-select form-select-sm"
              >
                <option
                  v-for="city in filterData.cities"
                  :key="city.id"
                  :value="city.id"
                >
                  {{ city.name }}
                </option>
              </select>
              <span v-else>{{ device.city }}</span>
            </td>

            <!-- Адрес -->
            <td>
              <input
                v-if="editingId === device.id"
                v-model="editForm.address"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.address }}</span>
            </td>

            <!-- Кабинет -->
            <td>
              <input
                v-if="editingId === device.id"
                v-model="editForm.room_number"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.room_number }}</span>
            </td>

            <!-- Производитель -->
            <td>
              <select
                v-if="editingId === device.id"
                v-model="editForm.manufacturer_id"
                class="form-select form-select-sm"
                @change="loadModelsForManufacturer"
              >
                <option
                  v-for="mfr in filterData.manufacturers"
                  :key="mfr.id"
                  :value="mfr.id"
                >
                  {{ mfr.name }}
                </option>
              </select>
              <strong v-else>{{ device.manufacturer }}</strong>
            </td>

            <!-- Модель -->
            <td>
              <select
                v-if="editingId === device.id"
                v-model="editForm.model_id"
                class="form-select form-select-sm"
                :disabled="!editForm.manufacturer_id"
              >
                <option
                  v-for="model in availableModels"
                  :key="model.id"
                  :value="model.id"
                >
                  {{ model.name }}
                </option>
              </select>
              <span v-else>{{ device.model }}</span>
            </td>

            <!-- Серийный номер -->
            <td>
              <input
                v-if="editingId === device.id"
                v-model="editForm.serial_number"
                type="text"
                class="form-control form-control-sm"
              />
              <code v-else>{{ device.serial_number || '—' }}</code>
            </td>

            <!-- Статус -->
            <td>
              <select
                v-if="editingId === device.id"
                v-model="editForm.status_id"
                class="form-select form-select-sm"
              >
                <option
                  v-for="status in filterData.statuses"
                  :key="status.id"
                  :value="status.id"
                >
                  {{ status.name }}
                </option>
              </select>
              <span
                v-else
                class="badge"
                :style="{ backgroundColor: device.status_color, color: '#fff' }"
              >
                {{ device.status }}
              </span>
            </td>

            <!-- Месяц обслуживания -->
            <td>
              <input
                v-if="editingId === device.id"
                v-model="editForm.service_start_month"
                type="month"
                class="form-control form-control-sm"
              />
              <small v-else>{{ device.service_start_month || '—' }}</small>
            </td>

            <!-- Действия -->
            <td>
              <div v-if="editingId === device.id" class="btn-group btn-group-sm" role="group">
                <button
                  class="btn btn-outline-success"
                  title="Сохранить"
                  @click="saveEdit(device.id)"
                  :disabled="isSaving"
                >
                  <i class="bi bi-check2"></i>
                </button>
                <button
                  class="btn btn-outline-secondary"
                  title="Отмена"
                  @click="cancelEdit"
                  :disabled="isSaving"
                >
                  <i class="bi bi-x"></i>
                </button>
              </div>
              <div v-else class="btn-group btn-group-sm" role="group">
                <button
                  class="btn btn-outline-primary"
                  title="Редактировать"
                  @click="startEdit(device)"
                >
                  <i class="bi bi-pencil"></i>
                </button>
                <button
                  class="btn btn-outline-danger"
                  title="Удалить"
                  @click="$emit('delete', device)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Комментарии -->
    <div v-if="devices.length" class="mt-2">
      <small class="text-muted">
        <i class="bi bi-info-circle me-1"></i>
        Всего устройств: {{ devices.length }}
      </small>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useToast } from '../../composables/useToast'
import { useColumnResize } from '../../composables/useColumnResize'

const tableRef = ref(null)

// Initialize column resizing
useColumnResize(tableRef, 'contracts:columnWidths')

const props = defineProps({
  devices: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  filterData: {
    type: Object,
    default: () => ({
      organizations: [],
      cities: [],
      manufacturers: [],
      statuses: []
    })
  }
})

const emit = defineEmits(['edit', 'delete', 'saved'])

const { showToast } = useToast()

const editingId = ref(null)
const isSaving = ref(false)
const availableModels = ref([])
const editForm = reactive({
  organization_id: '',
  city_id: '',
  address: '',
  room_number: '',
  manufacturer_id: '',
  model_id: '',
  serial_number: '',
  status_id: '',
  service_start_month: '',
  comment: ''
})

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function startEdit(device) {
  editingId.value = device.id

  // Populate form with device data
  editForm.organization_id = device.organization_id
  editForm.city_id = device.city_id
  editForm.address = device.address
  editForm.room_number = device.room_number
  editForm.serial_number = device.serial_number
  editForm.status_id = device.status_id
  editForm.service_start_month = device.service_start_month_iso || ''
  editForm.comment = device.comment || ''

  // Find manufacturer by name and load models
  const manufacturer = props.filterData.manufacturers.find(m => m.name === device.manufacturer)
  if (manufacturer) {
    editForm.manufacturer_id = manufacturer.id
    loadModelsForManufacturer()
  }
  editForm.model_id = device.model_id
}

function cancelEdit() {
  editingId.value = null
  availableModels.value = []
}

async function loadModelsForManufacturer() {
  if (!editForm.manufacturer_id) {
    availableModels.value = []
    editForm.model_id = ''
    return
  }

  try {
    const response = await fetch(
      `/contracts/api/models-by-manufacturer/?manufacturer_id=${editForm.manufacturer_id}`
    )
    const data = await response.json()
    availableModels.value = data.models || []
  } catch (error) {
    console.error('Error loading models:', error)
    showToast('Ошибка', 'Не удалось загрузить модели', 'error')
  }
}

async function saveEdit(deviceId) {
  isSaving.value = true

  try {
    const payload = {
      organization_id: parseInt(editForm.organization_id),
      city_id: parseInt(editForm.city_id),
      address: editForm.address,
      room_number: editForm.room_number,
      model_id: parseInt(editForm.model_id),
      serial_number: editForm.serial_number,
      status_id: parseInt(editForm.status_id),
      service_start_month: editForm.service_start_month || null,
      comment: editForm.comment
    }

    const response = await fetch(`/contracts/api/${deviceId}/update/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()

    if (data.ok) {
      showToast('Успех', 'Устройство обновлено', 'success')
      emit('saved')
      editingId.value = null
      availableModels.value = []
    } else {
      showToast('Ошибка', data.error || 'Не удалось сохранить изменения', 'error')
    }
  } catch (error) {
    console.error('Error saving device:', error)
    showToast('Ошибка', 'Не удалось сохранить устройство', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.contract-device-table {
  background: white;
  border-radius: 0.375rem;
  box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
}

.table-responsive-fixed {
  overflow-x: auto;
  overflow-y: visible;
}

.table {
  margin-bottom: 0;
}

.table-fixed {
  table-layout: fixed;
}

.table-fixed th,
.table-fixed td {
  word-wrap: break-word;
  overflow-wrap: anywhere;
}

.table th {
  font-weight: 600;
  font-size: 0.875rem;
  color: #495057;
  border-bottom: 2px solid #dee2e6;
}

.table td {
  vertical-align: middle;
  font-size: 0.875rem;
}

.table tbody tr:hover:not(.editing) {
  background-color: rgba(0, 123, 255, 0.05);
}

.table tbody tr.editing {
  background-color: rgba(13, 110, 253, 0.05);
}

.table tbody tr.editing td {
  padding: 0.375rem;
}

code {
  font-size: 0.8125rem;
  padding: 0.125rem 0.25rem;
  background: #f8f9fa;
  border-radius: 0.25rem;
}

.badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}

.btn-group-sm .btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.form-control-sm,
.form-select-sm {
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
}

/* Column resize handles */
:deep(.col-resize-handle) {
  position: absolute;
  top: 0;
  right: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  user-select: none;
  z-index: 1;
}

:deep(.col-resize-handle::after) {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  right: 2px;
  border-right: 1px dashed rgba(0, 0, 0, 0.2);
}

:deep(.col-resize-handle.active::after) {
  border-right-color: var(--bs-primary);
  border-right-width: 2px;
  border-right-style: solid;
}

:deep(.col-resize-handle:hover::after) {
  border-right-color: rgba(0, 123, 255, 0.5);
}
</style>
