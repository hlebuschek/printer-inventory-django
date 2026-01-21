<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="modal fade show d-block"
      tabindex="-1"
      aria-labelledby="printerModalLabel"
      aria-modal="true"
      role="dialog"
      @click.self="close"
    >
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="printerModalLabel">
              {{ modalTitle }}
            </h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <div class="modal-body">
            <!-- Tabs -->
            <ul class="nav nav-tabs" role="tablist">
              <li class="nav-item" role="presentation">
                <button
                  class="nav-link"
                  :class="{ active: activeTab === 'info' }"
                  type="button"
                  role="tab"
                  @click="activeTab = 'info'"
                >
                  Информация
                </button>
              </li>
              <li class="nav-item" role="presentation">
                <button
                  class="nav-link"
                  :class="{ active: activeTab === 'history' }"
                  type="button"
                  role="tab"
                  @click="activeTab = 'history'"
                >
                  История опросов
                </button>
              </li>
              <li v-if="permissions.view_entity_changes" class="nav-item" role="presentation">
                <button
                  class="nav-link"
                  :class="{ active: activeTab === 'changes' }"
                  type="button"
                  role="tab"
                  @click="activeTab = 'changes'"
                >
                  История изменений
                </button>
              </li>
            </ul>

            <!-- Tab Content -->
            <div class="tab-content mt-3">
              <!-- Info Tab -->
              <div
                v-show="activeTab === 'info'"
                class="tab-pane fade"
                :class="{ 'show active': activeTab === 'info' }"
                role="tabpanel"
              >
                <form @submit.prevent="savePrinter">
                  <div class="mb-3">
                    <label for="ip_address" class="form-label">IP-адрес</label>
                    <input
                      id="ip_address"
                      v-model="formData.ip_address"
                      type="text"
                      class="form-control"
                      :disabled="!permissions.change_printer"
                      required
                    />
                  </div>

                  <div class="mb-3">
                    <label for="serial_number" class="form-label">Серийный №</label>
                    <input
                      id="serial_number"
                      v-model="formData.serial_number"
                      type="text"
                      class="form-control"
                      :disabled="!permissions.change_printer"
                      required
                    />
                  </div>

                  <div class="mb-3">
                    <label for="mac_address" class="form-label">MAC-адрес</label>
                    <input
                      id="mac_address"
                      v-model="formData.mac_address"
                      type="text"
                      class="form-control"
                      :disabled="!permissions.change_printer"
                    />
                  </div>

                  <div class="row g-2 mb-3">
                    <div class="col">
                      <label for="manufacturer" class="form-label">Производитель</label>
                      <select
                        id="manufacturer"
                        v-model="formData.manufacturer"
                        class="form-select"
                        :disabled="!permissions.change_printer"
                        @change="onManufacturerChange"
                      >
                        <option value="">— выберите —</option>
                        <option
                          v-for="mfr in manufacturers"
                          :key="mfr.id"
                          :value="mfr.id"
                        >
                          {{ mfr.name }}
                        </option>
                      </select>
                    </div>

                    <div class="col">
                      <label for="device_model" class="form-label">Модель</label>
                      <select
                        id="device_model"
                        v-model="formData.device_model"
                        class="form-select"
                        :disabled="!permissions.change_printer"
                      >
                        <option value="">— выберите —</option>
                        <option
                          v-for="model in filteredModels"
                          :key="model.id"
                          :value="model.id"
                        >
                          {{ model.name }}
                        </option>
                      </select>
                    </div>
                  </div>

                  <div class="mb-3">
                    <label for="snmp_community" class="form-label">SNMP Community</label>
                    <input
                      id="snmp_community"
                      v-model="formData.snmp_community"
                      type="text"
                      class="form-control"
                      :disabled="!permissions.change_printer"
                      required
                    />
                  </div>

                  <div class="mb-3">
                    <label for="organization" class="form-label">Организация</label>
                    <select
                      id="organization"
                      v-model="formData.organization"
                      class="form-select"
                      :disabled="!permissions.change_printer"
                      required
                    >
                      <option value="">— выберите организацию —</option>
                      <option
                        v-for="org in organizations"
                        :key="org.id"
                        :value="org.id"
                      >
                        {{ org.name }}
                      </option>
                    </select>
                  </div>

                  <div v-if="!permissions.change_printer" class="alert alert-info">
                    У вас нет прав на редактирование — доступен только просмотр.
                  </div>
                </form>
              </div>

              <!-- History Tab -->
              <div
                v-show="activeTab === 'history'"
                class="tab-pane fade"
                :class="{ 'show active': activeTab === 'history' }"
                role="tabpanel"
              >
                <HistoryChart v-if="historyData.length" :history-data="historyData" />

                <div class="mt-3">
                  <h6>История опросов</h6>
                  <div class="table-responsive">
                    <table class="table table-striped table-bordered">
                      <thead>
                        <tr>
                          <th>Дата</th>
                          <th>ЧБ A4</th>
                          <th>Цвет A4</th>
                          <th>ЧБ A3</th>
                          <th>Цвет A3</th>
                          <th>Всего</th>
                          <th>Тонер (K/C/M/Y)</th>
                          <th>Барабан (K/C/M/Y)</th>
                          <th>Fuser Kit</th>
                          <th>Transfer Kit</th>
                          <th>Waste Toner</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="row in historyData" :key="row.task_timestamp">
                          <td>{{ formatDate(row.task_timestamp) }}</td>
                          <td>{{ row.bw_a4 || '—' }}</td>
                          <td>{{ row.color_a4 || '—' }}</td>
                          <td>{{ row.bw_a3 || '—' }}</td>
                          <td>{{ row.color_a3 || '—' }}</td>
                          <td>{{ row.total_pages || '—' }}</td>
                          <td>
                            {{ row.toner_black || '—' }}/{{ row.toner_cyan || '—' }}/{{ row.toner_magenta || '—' }}/{{ row.toner_yellow || '—' }}
                          </td>
                          <td>
                            {{ row.drum_black || '—' }}/{{ row.drum_cyan || '—' }}/{{ row.drum_magenta || '—' }}/{{ row.drum_yellow || '—' }}
                          </td>
                          <td>{{ row.fuser_kit || '—' }}</td>
                          <td>{{ row.transfer_kit || '—' }}</td>
                          <td>{{ row.waste_toner || '—' }}</td>
                        </tr>
                        <tr v-if="!historyData.length">
                          <td colspan="11" class="text-center">Нет данных</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <!-- Change History Tab -->
              <div
                v-if="permissions.view_entity_changes"
                v-show="activeTab === 'changes'"
                class="tab-pane fade"
                :class="{ 'show active': activeTab === 'changes' }"
                role="tabpanel"
              >
                <!-- Loading state -->
                <div v-if="changeHistoryLoading" class="text-center py-5">
                  <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                  </div>
                </div>

                <!-- Error state -->
                <div v-else-if="changeHistoryError" class="alert alert-danger" role="alert">
                  <strong>Ошибка:</strong> {{ changeHistoryError }}
                </div>

                <!-- Empty state -->
                <div v-else-if="!changeHistory || changeHistory.length === 0" class="text-center py-5 text-muted">
                  <p>История изменений пуста</p>
                </div>

                <!-- Change history timeline -->
                <div v-else class="timeline">
                  <div
                    v-for="log in changeHistory"
                    :key="log.id"
                    class="timeline-item mb-4"
                    :class="getChangeActionClass(log.action)"
                  >
                    <div class="card">
                      <div class="card-header d-flex justify-content-between align-items-center">
                        <div>
                          <span class="badge" :class="getChangeActionBadgeClass(log.action)">
                            <i :class="getChangeActionIcon(log.action)"></i> {{ log.action_display }}
                          </span>
                          <strong class="ms-2">{{ log.user }}</strong>
                        </div>
                        <small class="text-muted">
                          {{ formatChangeDateTime(log.timestamp) }}
                          <span v-if="log.ip_address" class="ms-2">
                            <i class="bi bi-globe"></i> {{ log.ip_address }}
                          </span>
                        </small>
                      </div>

                      <div v-if="log.changes && log.changes.length > 0" class="card-body">
                        <table class="table table-sm table-borderless mb-0">
                          <thead>
                            <tr>
                              <th style="width: 30%">Поле</th>
                              <th style="width: 35%">Старое значение</th>
                              <th style="width: 35%">Новое значение</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(change, idx) in log.changes" :key="idx">
                              <td class="fw-bold">{{ change.label }}</td>
                              <td>
                                <span class="text-muted" v-if="change.old === '—'">—</span>
                                <code v-else class="bg-light px-2 py-1 rounded">{{ change.old }}</code>
                              </td>
                              <td>
                                <span class="text-muted" v-if="change.new === '—'">—</span>
                                <code v-else class="bg-success bg-opacity-10 px-2 py-1 rounded text-success">
                                  {{ change.new }}
                                </code>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div v-else class="card-body">
                        <p class="text-muted mb-0">Нет подробностей изменений</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="close">
              Закрыть
            </button>
            <button
              v-if="activeTab === 'info' && permissions.change_printer"
              type="button"
              class="btn btn-primary"
              :disabled="isSaving"
              @click="savePrinter"
            >
              <span
                v-if="isSaving"
                class="spinner-border spinner-border-sm me-2"
              ></span>
              <i v-else class="bi bi-save me-1"></i>
              {{ isSaving ? 'Сохранение...' : 'Обновить' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal backdrop -->
    <div v-if="show" class="modal-backdrop fade show"></div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useToast } from '../../composables/useToast'
import HistoryChart from './HistoryChart.vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  printerId: {
    type: Number,
    default: null
  },
  mode: {
    type: String,
    default: 'edit' // 'edit' or 'history'
  },
  organizations: {
    type: Array,
    default: () => []
  },
  permissions: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:show', 'updated'])

const { showToast } = useToast()

const activeTab = ref('info')
const isSaving = ref(false)
const isLoading = ref(false)
const historyData = ref([])
const manufacturers = ref([])
const allModels = ref([])
const changeHistory = ref([])
const changeHistoryLoading = ref(false)
const changeHistoryError = ref(null)

const formData = reactive({
  ip_address: '',
  serial_number: '',
  mac_address: '',
  manufacturer: '',
  device_model: '',
  snmp_community: '',
  organization: ''
})

const modalTitle = computed(() => {
  return formData.ip_address ? `Принтер ${formData.ip_address}` : 'Информация о принтере'
})

const filteredModels = computed(() => {
  if (!formData.manufacturer) {
    return allModels.value
  }

  return allModels.value.filter(
    model => String(model.manufacturer_id) === String(formData.manufacturer)
  )
})

function onManufacturerChange() {
  // Clear device model when manufacturer changes
  if (!formData.manufacturer) {
    formData.device_model = ''
  }
}

async function loadPrinterData() {
  if (!props.printerId) return

  isLoading.value = true

  try {
    const response = await fetch(`/inventory/api/printer/${props.printerId}/`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    // Update form data
    formData.ip_address = data.ip_address || ''
    formData.serial_number = data.serial_number || ''
    formData.mac_address = data.mac_address || ''
    formData.manufacturer = data.manufacturer_id || ''
    formData.device_model = data.device_model_id || ''
    formData.snmp_community = data.snmp_community || ''
    formData.organization = data.organization_id || ''
  } catch (error) {
    console.error('Error loading printer data:', error)
    showToast('Ошибка', 'Не удалось загрузить данные принтера', 'error')
  } finally {
    isLoading.value = false
  }
}

async function loadHistoryData() {
  if (!props.printerId) return

  try {
    const response = await fetch(`/inventory/${props.printerId}/history/`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    historyData.value = await response.json()
  } catch (error) {
    console.error('Error loading history data:', error)
    showToast('Ошибка', 'Не удалось загрузить историю', 'error')
  }
}

async function loadChangeHistory() {
  if (!props.printerId || !props.permissions.view_entity_changes) return

  changeHistoryLoading.value = true
  changeHistoryError.value = null

  try {
    const response = await fetch(`/inventory/${props.printerId}/change-history/`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    changeHistory.value = data.history || []
  } catch (error) {
    console.error('Error loading change history:', error)
    changeHistoryError.value = error.message || 'Не удалось загрузить историю изменений'
  } finally {
    changeHistoryLoading.value = false
  }
}

async function loadAllModels() {
  try {
    const response = await fetch('/inventory/api/all-printer-models/')
    const data = await response.json()

    allModels.value = data.models || []

    // Extract unique manufacturers
    const mfrMap = new Map()
    allModels.value.forEach(m => {
      if (!mfrMap.has(m.manufacturer_id)) {
        mfrMap.set(m.manufacturer_id, {
          id: m.manufacturer_id,
          name: m.manufacturer
        })
      }
    })

    manufacturers.value = Array.from(mfrMap.values()).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  } catch (error) {
    console.error('Error loading models:', error)
  }
}

async function savePrinter() {
  if (!props.printerId) return

  isSaving.value = true

  try {
    const formDataToSend = new FormData()
    Object.keys(formData).forEach(key => {
      // Send all fields, even empty ones (form validation will handle required fields)
      formDataToSend.append(key, formData[key] || '')
    })

    const response = await fetch(`/inventory/${props.printerId}/edit/`, {
      method: 'POST',
      body: formDataToSend,
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      }
    })

    const data = await response.json()

    if (response.ok && data.success) {
      showToast('Успех', 'Принтер обновлён', 'success')
      emit('updated')
      close()
    } else {
      // Parse Django form errors
      let errorMessage = 'Не удалось обновить принтер'
      if (data.error) {
        try {
          const errors = JSON.parse(data.error)
          const errorMessages = Object.entries(errors).map(([field, msgs]) => {
            const fieldName = field === '__all__' ? 'Общая ошибка' : field
            return `${fieldName}: ${msgs.map(m => m.message).join(', ')}`
          })
          errorMessage = errorMessages.join('; ')
        } catch (e) {
          errorMessage = data.error
        }
      }
      showToast('Ошибка', errorMessage, 'error')
    }
  } catch (error) {
    console.error('Error saving printer:', error)
    showToast('Ошибка', 'Не удалось сохранить изменения', 'error')
  } finally {
    isSaving.value = false
  }
}

function formatDate(dateString) {
  if (!dateString) return '—'

  try {
    const date = new Date(dateString)
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateString
  }
}

function formatChangeDateTime(isoString) {
  if (!isoString) return ''

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  // Relative time for recent changes
  if (diffMins < 1) return 'только что'
  if (diffMins < 60) return `${diffMins} мин. назад`
  if (diffHours < 24) return `${diffHours} ч. назад`
  if (diffDays < 7) return `${diffDays} дн. назад`

  // Full date for older changes
  return date.toLocaleString('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getChangeActionClass(action) {
  const classes = {
    create: 'timeline-item-create',
    update: 'timeline-item-update',
    delete: 'timeline-item-delete'
  }
  return classes[action] || ''
}

function getChangeActionBadgeClass(action) {
  const classes = {
    create: 'bg-success',
    update: 'bg-primary',
    delete: 'bg-danger'
  }
  return classes[action] || 'bg-secondary'
}

function getChangeActionIcon(action) {
  const icons = {
    create: 'bi bi-plus-circle',
    update: 'bi bi-pencil',
    delete: 'bi bi-trash'
  }
  return icons[action] || 'bi bi-file-text'
}

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function close() {
  emit('update:show', false)
}

// Watch for modal open
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      // Set active tab based on mode
      activeTab.value = props.mode === 'history' ? 'history' : 'info'

      // Load data
      if (props.printerId) {
        loadPrinterData()
        loadHistoryData()
        loadAllModels()
        if (props.permissions.view_entity_changes) {
          loadChangeHistory()
        }
      }
    }
  }
)
</script>

<style scoped>
.modal {
  background: rgba(0, 0, 0, 0.5);
}

/* Change history timeline styles */
.timeline {
  position: relative;
}

.timeline-item {
  position: relative;
  padding-left: 40px;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: -30px;
  width: 2px;
  background: #dee2e6;
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-item-create::after {
  content: '\f4fe'; /* Bootstrap icon bi-plus-circle */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #198754;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

.timeline-item-update::after {
  content: '\f4ca'; /* Bootstrap icon bi-pencil */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #0d6efd;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

.timeline-item-delete::after {
  content: '\f5de'; /* Bootstrap icon bi-trash */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #dc3545;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

code {
  font-size: 0.875em;
}

.table th {
  font-weight: 600;
  color: #6c757d;
  border-bottom: 2px solid #dee2e6;
}
</style>
