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

    <div v-else class="table-responsive">
      <table ref="tableRef" class="table table-sm table-striped table-hover table-bordered align-middle table-fixed table-resizable">
        <colgroup>
          <col style="width: 70px;">
          <col :class="['cg-org', { 'd-none': !isColumnVisible('org') }]" style="width: 220px;">
          <col :class="['cg-city', { 'd-none': !isColumnVisible('city') }]" style="width: 160px;">
          <col :class="['cg-address', { 'd-none': !isColumnVisible('address') }]" style="width: 280px;">
          <col :class="['cg-room', { 'd-none': !isColumnVisible('room') }]" style="width: 130px;">
          <col :class="['cg-mfr', { 'd-none': !isColumnVisible('mfr') }]" style="width: 200px;">
          <col :class="['cg-model', { 'd-none': !isColumnVisible('model') }]" style="width: 260px;">
          <col :class="['cg-serial', { 'd-none': !isColumnVisible('serial') }]" style="width: 190px;">
          <col :class="['cg-service_month', { 'd-none': !isColumnVisible('service_month') }]" style="width: 140px;">
          <col :class="['cg-status', { 'd-none': !isColumnVisible('status') }]" style="width: 220px;">
          <col :class="['cg-comment', { 'd-none': !isColumnVisible('comment') }]">
          <col class="cg-actions" style="width: 200px;">
        </colgroup>

        <thead class="table-light">
          <tr>
            <th>№</th>
            <th :class="['th-org', { 'd-none': !isColumnVisible('org') }]">Организация</th>
            <th :class="['th-city', { 'd-none': !isColumnVisible('city') }]">Город</th>
            <th :class="['th-address', { 'd-none': !isColumnVisible('address') }]">Адрес</th>
            <th :class="['th-room', { 'd-none': !isColumnVisible('room') }]">№ кабинета</th>
            <th :class="['th-mfr', { 'd-none': !isColumnVisible('mfr') }]">Производитель</th>
            <th :class="['th-model', { 'd-none': !isColumnVisible('model') }]">Модель оборудования</th>
            <th :class="['th-serial', { 'd-none': !isColumnVisible('serial') }]">Серийный номер</th>
            <th :class="['th-service_month', { 'd-none': !isColumnVisible('service_month') }]">Месяц обслуживания</th>
            <th :class="['th-status', { 'd-none': !isColumnVisible('status') }]">Статус</th>
            <th :class="['th-comment', { 'd-none': !isColumnVisible('comment') }]">Комментарий</th>
            <th class="text-center th-actions">Действия</th>
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
            <td :class="['col-org', { 'd-none': !isColumnVisible('org') }]">
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
            <td :class="['col-city', { 'd-none': !isColumnVisible('city') }]">
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
            <td :class="['col-address addr', { 'd-none': !isColumnVisible('address') }]">
              <input
                v-if="editingId === device.id"
                v-model="editForm.address"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.address }}</span>
            </td>

            <!-- Кабинет -->
            <td :class="['col-room', { 'd-none': !isColumnVisible('room') }]">
              <input
                v-if="editingId === device.id"
                v-model="editForm.room_number"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.room_number }}</span>
            </td>

            <!-- Производитель -->
            <td :class="['col-mfr', { 'd-none': !isColumnVisible('mfr') }]">
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
              <span v-else>{{ device.manufacturer }}</span>
            </td>

            <!-- Модель -->
            <td :class="['col-model', { 'd-none': !isColumnVisible('model') }]">
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
            <td :class="['col-serial', { 'd-none': !isColumnVisible('serial') }]">
              <input
                v-if="editingId === device.id"
                v-model="editForm.serial_number"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.serial_number || '—' }}</span>
            </td>

            <!-- Месяц обслуживания -->
            <td :class="['col-service-month', { 'd-none': !isColumnVisible('service_month') }]">
              <input
                v-if="editingId === device.id"
                v-model="editForm.service_start_month"
                type="month"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.service_start_month || '—' }}</span>
            </td>

            <!-- Статус -->
            <td :class="['col-status', { 'd-none': !isColumnVisible('status') }]">
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
                v-else-if="device.status"
                class="badge rounded-pill"
                :style="{ backgroundColor: device.status_color, color: '#fff' }"
              >
                {{ device.status }}
              </span>
              <span v-else>—</span>
            </td>

            <!-- Комментарий -->
            <td :class="['col-comment comment', { 'd-none': !isColumnVisible('comment') }]">
              <textarea
                v-if="editingId === device.id"
                v-model="editForm.comment"
                class="form-control form-control-sm"
                rows="2"
              ></textarea>
              <span v-else>{{ device.comment }}</span>
            </td>

            <!-- Действия -->
            <td class="col-actions">
              <div v-if="editingId === device.id" class="btn-group btn-group-sm action-group" role="group">
                <button
                  class="btn btn-outline-success btn-icon"
                  title="Сохранить"
                  @click="saveEdit(device.id)"
                  :disabled="isSaving"
                >
                  <i class="bi bi-check2"></i>
                </button>
                <button
                  class="btn btn-outline-secondary btn-icon"
                  title="Отмена"
                  @click="cancelEdit"
                  :disabled="isSaving"
                >
                  <i class="bi bi-x"></i>
                </button>
              </div>
              <div v-else class="btn-group btn-group-sm action-group" role="group">
                <button
                  v-if="permissions.change_contractdevice"
                  class="btn btn-outline-secondary btn-icon"
                  title="Редактировать"
                  @click="startEdit(device)"
                >
                  <i class="bi bi-pencil"></i>
                </button>
                <button
                  v-if="permissions.delete_contractdevice"
                  class="btn btn-outline-danger btn-icon"
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
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useToast } from '../../composables/useToast'
import { useColumnResize } from '../../composables/useColumnResize'

const tableRef = ref(null)

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
  },
  columns: {
    type: Array,
    default: () => []
  },
  permissions: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['edit', 'delete', 'saved'])

const { showToast } = useToast()

// Initialize column resizing
useColumnResize(tableRef, 'contracts:columnWidths')

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

function isColumnVisible(key) {
  const column = props.columns.find(col => col.key === key)
  return column ? column.visible : true
}

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
/* таблица + заголовки */
.table-fixed {
  table-layout: fixed;
}

.table-fixed th,
.table-fixed td {
  vertical-align: middle;
}

.table-fixed thead th {
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  position: relative;
  padding-right: 10px; /* место под ручку */
}

/* ВАЖНО: позволяем вертикально выходить меню за пределы .table-responsive,
   но горизонтальный скролл таблицы сохраняем */
.table-responsive {
  overflow-x: auto;
  overflow-y: visible;
}

/* тело таблицы — переносы */
.table-fixed tbody td {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
}

/* узкие ячейки — без переносов */
.table-fixed td.col-serial,
.table-fixed td.col-room,
.table-fixed td.col-status,
.table-fixed td.col-service-month,
.table-fixed td.col-actions {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* кнопки действий */
.col-actions {
  text-align: center;
  white-space: nowrap;
}

.action-group .btn-icon {
  width: 2rem;
  height: 2rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.action-group .btn-icon i {
  font-size: 1rem;
  line-height: 1;
}

/* подсветка редактируемой строки */
tr.editing {
  background: rgba(13, 110, 253, 0.05);
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

.form-control-sm,
.form-select-sm {
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
}

.badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}
</style>
