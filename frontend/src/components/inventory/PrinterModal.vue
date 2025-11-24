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
                  История
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
      }
    }
  }
)
</script>

<style scoped>
.modal {
  background: rgba(0, 0, 0, 0.5);
}
</style>
