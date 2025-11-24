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
              <select
                v-model="formData.organization_id"
                class="form-select"
                :class="{ 'is-invalid': errors.organization_id }"
                required
              >
                <option value="">Выберите организацию</option>
                <option
                  v-for="org in filterData.organizations"
                  :key="org.id"
                  :value="org.id"
                >
                  {{ org.name }}
                </option>
              </select>
              <div v-if="errors.organization_id" class="invalid-feedback">
                {{ errors.organization_id }}
              </div>
            </div>

            <!-- Город -->
            <div class="mb-3">
              <label class="form-label">Город <span class="text-danger">*</span></label>
              <select
                v-model="formData.city_id"
                class="form-select"
                :class="{ 'is-invalid': errors.city_id }"
                required
              >
                <option value="">Выберите город</option>
                <option v-for="city in filterData.cities" :key="city.id" :value="city.id">
                  {{ city.name }}
                </option>
              </select>
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
                <select
                  v-model="selectedManufacturerId"
                  class="form-select"
                  :class="{ 'is-invalid': errors.manufacturer }"
                  @change="loadModels"
                  required
                >
                  <option value="">Выберите производителя</option>
                  <option
                    v-for="mfr in filterData.manufacturers"
                    :key="mfr.id"
                    :value="mfr.id"
                  >
                    {{ mfr.name }}
                  </option>
                </select>
                <div v-if="errors.manufacturer" class="invalid-feedback">
                  {{ errors.manufacturer }}
                </div>
              </div>

              <div class="col-md-6 mb-3">
                <label class="form-label">Модель <span class="text-danger">*</span></label>
                <select
                  v-model="formData.model_id"
                  class="form-select"
                  :class="{ 'is-invalid': errors.model_id }"
                  :disabled="!selectedManufacturerId"
                  required
                >
                  <option value="">Выберите модель</option>
                  <option v-for="model in availableModels" :key="model.id" :value="model.id">
                    {{ model.name }}
                  </option>
                </select>
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
              <select
                v-model="formData.status_id"
                class="form-select"
                :class="{ 'is-invalid': errors.status_id }"
                required
              >
                <option value="">Выберите статус</option>
                <option v-for="status in filterData.statuses" :key="status.id" :value="status.id">
                  {{ status.name }}
                </option>
              </select>
              <div v-if="errors.status_id" class="invalid-feedback">
                {{ errors.status_id }}
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
      statuses: []
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

const formData = reactive({
  organization_id: '',
  city_id: '',
  address: '',
  room_number: '',
  model_id: '',
  serial_number: '',
  status_id: '',
  service_start_month: '',
  comment: ''
})

// Computed
const isEdit = computed(() => !!props.device)

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
  formData.service_start_month = ''
  formData.comment = ''
  selectedManufacturerId.value = ''
  availableModels.value = []
  clearErrors()
}

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
      service_start_month: formData.service_start_month || null,
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
      formData.service_start_month = newDevice.service_start_month_iso || ''
      formData.comment = newDevice.comment

      // Определяем производителя по модели
      const manufacturer = props.filterData.manufacturers.find(m =>
        m.name === newDevice.manufacturer
      )
      if (manufacturer) {
        selectedManufacturerId.value = manufacturer.id
        loadModels()
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
