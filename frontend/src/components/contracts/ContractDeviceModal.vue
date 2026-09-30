<template>
  <div v-if="show" class="modal fade show" style="display: block" tabindex="-1">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            {{ isEdit ? 'Редактировать устройство' : 'Добавить устройство' }}
          </h5>
          <button type="button" class="btn-close" @click="closeModal"></button>
        </div>

        <div class="modal-body">
          <form @submit.prevent="handleSubmit">
            <!-- Организация -->
            <div class="mb-3">
              <label class="form-label">Организация <span class="text-danger">*</span></label>
              <SearchableSelect
                v-model="formData.organization_id"
                :options="organizationOptions"
                placeholder="Выберите организацию"
                :invalid="!!errors.organization_id"
              />
              <div v-if="errors.organization_id" class="invalid-feedback">
                {{ errors.organization_id }}
              </div>
            </div>

            <!-- Город -->
            <div class="mb-3">
              <label class="form-label">Город <span class="text-danger">*</span></label>
              <SearchableSelect
                v-model="formData.city_id"
                :options="cityOptions"
                placeholder="Выберите город"
                :invalid="!!errors.city_id"
              />
              <div v-if="errors.city_id" class="invalid-feedback">
                {{ errors.city_id }}
              </div>
            </div>

            <!-- Адрес -->
            <div class="mb-3">
              <label class="form-label">Адрес <span class="text-danger">*</span></label>
              <input
                v-model="formData.address"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.address }"
                required
              />
              <div v-if="errors.address" class="invalid-feedback">
                {{ errors.address }}
              </div>
            </div>

            <!-- Кабинет -->
            <div class="mb-3">
              <label class="form-label">№ кабинета</label>
              <input
                v-model="formData.room_number"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.room_number }"
              />
              <div v-if="errors.room_number" class="invalid-feedback">
                {{ errors.room_number }}
              </div>
            </div>

            <!-- Производитель и Модель -->
            <div class="row">
              <div class="col-md-6 mb-3">
                <label class="form-label">Производитель <span class="text-danger">*</span></label>
                <SearchableSelect
                  v-model="selectedManufacturerId"
                  :options="manufacturerOptions"
                  placeholder="Выберите производителя"
                  :invalid="!!errors.manufacturer"
                />
                <div v-if="errors.manufacturer" class="invalid-feedback">
                  {{ errors.manufacturer }}
                </div>
              </div>

              <div class="col-md-6 mb-3">
                <label class="form-label">Модель <span class="text-danger">*</span></label>
                <SearchableSelect
                  v-model="formData.model_id"
                  :options="modelOptions"
                  placeholder="Выберите модель"
                  :disabled="!selectedManufacturerId"
                  :invalid="!!errors.model_id"
                />
                <div v-if="errors.model_id" class="invalid-feedback">
                  {{ errors.model_id }}
                </div>
              </div>
            </div>

            <!-- Серийный номер -->
            <div class="mb-3">
              <label class="form-label">Серийный номер</label>
              <input
                v-model="formData.serial_number"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.serial_number }"
              />
              <div v-if="errors.serial_number" class="invalid-feedback">
                {{ errors.serial_number }}
              </div>
            </div>

            <!-- Статус -->
            <div class="mb-3">
              <label class="form-label">Статус <span class="text-danger">*</span></label>
              <SearchableSelect
                v-model="formData.status_id"
                :options="statusOptions"
                placeholder="Выберите статус"
                :invalid="!!errors.status_id"
              />
              <div v-if="errors.status_id" class="invalid-feedback">
                {{ errors.status_id }}
              </div>
            </div>

            <!-- Подрядчик -->
            <div class="mb-3">
              <label class="form-label">Подрядчик <span class="text-danger">*</span></label>
              <SearchableSelect
                v-model="formData.service_provider_id"
                :options="providerOptions"
                placeholder="Выберите подрядчика"
                :invalid="!!errors.service_provider_id"
              />
              <div class="form-text">Определяет, куда подаются заявки по устройству</div>
              <div v-if="errors.service_provider_id" class="invalid-feedback">
                {{ errors.service_provider_id }}
              </div>
            </div>

            <!-- Месяц принятия на обслуживание -->
            <div class="mb-3">
              <label class="form-label">Месяц принятия на обслуживание</label>
              <input
                v-model="formData.service_start_month"
                type="month"
                class="form-control"
                :class="{ 'is-invalid': errors.service_start_month }"
              />
              <div v-if="errors.service_start_month" class="invalid-feedback">
                {{ errors.service_start_month }}
              </div>
            </div>

            <!-- Счётчик при приёмке -->
            <div class="mb-3">
              <label class="form-label">Счётчик при приёмке</label>
              <input
                v-model="formData.initial_counter"
                type="number"
                min="0"
                class="form-control"
                :class="{ 'is-invalid': errors.initial_counter }"
              />
              <div class="form-text">Показание счётчика на момент принятия на обслуживание</div>
              <div v-if="errors.initial_counter" class="invalid-feedback">
                {{ errors.initial_counter }}
              </div>
            </div>

            <!-- Документы приёмки (PDF) -->
            <div class="mb-3">
              <label class="form-label">Документы приёмки (PDF)</label>
              <input
                ref="pdfInputRef"
                type="file"
                accept="application/pdf,.pdf"
                multiple
                class="form-control"
                @change="onPdfSelected"
              />
              <div class="form-text">Конфигурационная страница, акт приёмки и т.п. — можно несколько файлов</div>
            </div>

            <!-- Комментарий -->
            <div class="mb-3">
              <label class="form-label">Комментарий</label>
              <textarea
                v-model="formData.comment"
                class="form-control"
                :class="{ 'is-invalid': errors.comment }"
                rows="3"
              ></textarea>
              <div v-if="errors.comment" class="invalid-feedback">
                {{ errors.comment }}
              </div>
            </div>
          </form>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="closeModal">
            Отмена
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="isSaving"
            @click="handleSubmit"
          >
            <span v-if="isSaving" class="spinner-border spinner-border-sm me-2"></span>
            {{ isEdit ? 'Сохранить' : 'Создать' }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="show" class="modal-backdrop fade show"></div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useToast } from '../../composables/useToast'
import SearchableSelect from '../common/SearchableSelect.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  device: {
    type: Object,
    default: null
  },
  filterData: {
    type: Object,
    default: () => ({
      organizations: [],
      cities: [],
      manufacturers: [],
      statuses: [],
      providers: []
    })
  }
})

const emit = defineEmits(['update:show', 'saved'])

const { showToast } = useToast()

// State
const isSaving = ref(false)
const selectedManufacturerId = ref('')
const availableModels = ref([])
const errors = reactive({})
const pdfFiles = ref([])
const pdfInputRef = ref(null)

const formData = reactive({
  organization_id: '',
  city_id: '',
  address: '',
  room_number: '',
  model_id: '',
  serial_number: '',
  status_id: '',
  service_provider_id: '',
  service_start_month: '',
  initial_counter: '',
  comment: ''
})

// Computed
const isEdit = computed(() => !!props.device)

const toOptions = (items) => (items || []).map(i => ({ value: i.id, label: i.name }))
const organizationOptions = computed(() => toOptions(props.filterData.organizations))
const cityOptions = computed(() => toOptions(props.filterData.cities))
const manufacturerOptions = computed(() => toOptions(props.filterData.manufacturers))
const statusOptions = computed(() => toOptions(props.filterData.statuses))
const providerOptions = computed(() => toOptions(props.filterData.providers))
const modelOptions = computed(() => toOptions(availableModels.value))

// Methods
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function clearErrors() {
  Object.keys(errors).forEach(key => delete errors[key])
}

function resetForm() {
  formData.organization_id = ''
  formData.city_id = ''
  formData.address = ''
  formData.room_number = ''
  formData.model_id = ''
  formData.serial_number = ''
  formData.status_id = ''
  formData.service_provider_id = ''
  formData.service_start_month = ''
  formData.initial_counter = ''
  formData.comment = ''
  selectedManufacturerId.value = ''
  availableModels.value = []
  pdfFiles.value = []
  if (pdfInputRef.value) {
    pdfInputRef.value.value = ''
  }
  clearErrors()
}

function onPdfSelected(event) {
  const files = Array.from(event.target.files)
  const invalid = files.find(f => !f.name.toLowerCase().endsWith('.pdf'))
  if (invalid) {
    showToast('Ошибка', `«${invalid.name}»: допускается только PDF`, 'error')
    event.target.value = ''
    pdfFiles.value = []
    return
  }
  pdfFiles.value = files
}

watch(selectedManufacturerId, async () => {
  await loadModels()
  if (formData.model_id && !availableModels.value.some(m => m.id === formData.model_id)) {
    formData.model_id = ''
  }
})

async function loadModels() {
  if (!selectedManufacturerId.value) {
    availableModels.value = []
    formData.model_id = ''
    return
  }

  try {
    const response = await fetch(
      `/contracts/api/models-by-manufacturer/?manufacturer_id=${selectedManufacturerId.value}`
    )
    const data = await response.json()
    availableModels.value = data.models || []
  } catch (error) {
    console.error('Error loading models:', error)
    showToast('Ошибка', 'Не удалось загрузить модели', 'error')
  }
}

async function handleSubmit() {
  clearErrors()
  isSaving.value = true

  try {
    const url = isEdit.value
      ? `/contracts/api/${props.device.id}/update/`
      : '/contracts/api/create/'

    const payload = {
      organization_id: parseInt(formData.organization_id),
      city_id: parseInt(formData.city_id),
      address: formData.address,
      room_number: formData.room_number,
      model_id: parseInt(formData.model_id),
      serial_number: formData.serial_number,
      status_id: parseInt(formData.status_id),
      service_provider_id: parseInt(formData.service_provider_id),
      service_start_month: formData.service_start_month || null,
      initial_counter: formData.initial_counter === '' ? null : parseInt(formData.initial_counter),
      comment: formData.comment
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()

    if (data.ok) {
      const deviceId = isEdit.value ? props.device.id : data.device?.id
      if (pdfFiles.value.length && deviceId) {
        const fd = new FormData()
        pdfFiles.value.forEach(f => fd.append('files', f))
        const pdfResponse = await fetch(`/contracts/api/${deviceId}/acceptance-docs/upload/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCookie('csrftoken') },
          body: fd
        })
        const pdfData = await pdfResponse.json()
        if (!pdfData.ok) {
          showToast('Внимание', `Устройство сохранено, но PDF не загружен: ${pdfData.error || ''}`, 'warning')
          emit('saved')
          closeModal()
          return
        }
      }
      showToast('Успех', isEdit.value ? 'Устройство обновлено' : 'Устройство создано', 'success')
      emit('saved')
      closeModal()
    } else if (data.error) {
      // Обработка ошибок валидации
      if (typeof data.error === 'object') {
        Object.assign(errors, data.error)
      } else {
        showToast('Ошибка', data.error, 'error')
      }
    }
  } catch (error) {
    console.error('Error saving device:', error)
    showToast('Ошибка', 'Не удалось сохранить устройство', 'error')
  } finally {
    isSaving.value = false
  }
}

function closeModal() {
  emit('update:show', false)
  resetForm()
}

// Watch for device changes to populate form
watch(
  () => props.device,
  (newDevice) => {
    if (newDevice) {
      formData.organization_id = newDevice.organization_id
      formData.city_id = newDevice.city_id
      formData.address = newDevice.address
      formData.room_number = newDevice.room_number
      formData.model_id = newDevice.model_id
      formData.serial_number = newDevice.serial_number
      formData.status_id = newDevice.status_id
      formData.service_provider_id = newDevice.service_provider_id || ''
      formData.service_start_month = newDevice.service_start_month_iso || ''
      formData.initial_counter = newDevice.initial_counter ?? ''
      formData.comment = newDevice.comment

      // Определяем производителя по модели
      const manufacturer = props.filterData.manufacturers.find(m =>
        m.name === newDevice.manufacturer
      )
      if (manufacturer) {
        selectedManufacturerId.value = manufacturer.id
      }
    }
  },
  { immediate: true }
)

// Watch for modal close to reset form
watch(
  () => props.show,
  (newValue) => {
    if (!newValue) {
      resetForm()
    }
  }
)
</script>

<style scoped>
.modal {
  z-index: 1050;
}

.modal-backdrop {
  z-index: 1040;
}

.is-invalid {
  border-color: #dc3545;
}

.invalid-feedback {
  display: block;
}
</style>
