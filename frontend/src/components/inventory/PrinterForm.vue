<template>
  <div class="row justify-content-center">
    <div class="col-12 col-sm-10 col-md-8 col-lg-6 col-xl-5">
      <h2 class="mb-4">
        {{ isEdit ? 'Редактировать принтер' : 'Добавить принтер' }}
      </h2>

      <form @submit.prevent="handleSubmit" novalidate>
        <!-- Non-field errors -->
        <div v-if="formErrors.__all__" class="alert alert-danger">
          <div v-for="(error, idx) in formErrors.__all__" :key="idx">{{ error }}</div>
        </div>

        <!-- IP Address -->
        <div class="mb-3">
          <label for="ip_address" class="form-label">
            IP-адрес <span class="text-danger">*</span>
          </label>
          <input
            id="ip_address"
            v-model="formData.ip_address"
            type="text"
            class="form-control"
            :class="{ 'is-invalid': formErrors.ip_address }"
            required
          />
          <div v-if="formErrors.ip_address" class="invalid-feedback d-block">
            {{ formErrors.ip_address.join(', ') }}
          </div>
        </div>

        <!-- Serial Number -->
        <div class="mb-3">
          <label for="serial_number" class="form-label">
            Серийный номер <span class="text-danger">*</span>
          </label>
          <input
            id="serial_number"
            v-model="formData.serial_number"
            type="text"
            class="form-control"
            :class="{ 'is-invalid': formErrors.serial_number }"
            required
            @blur="lookupBySerial"
          />
          <div v-if="formErrors.serial_number" class="invalid-feedback d-block">
            {{ formErrors.serial_number.join(', ') }}
          </div>
        </div>

        <!-- Manufacturer and Model -->
        <div class="row g-2 mb-3">
          <div class="col">
            <label for="manufacturer" class="form-label">Производитель</label>
            <select
              id="manufacturer"
              v-model="selectedManufacturer"
              class="form-select"
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
            <SearchableSelect
              v-model="formData.device_model"
              :options="modelOptions"
              :disabled="!selectedManufacturer"
              :placeholder="selectedManufacturer ? 'Поиск модели…' : 'сначала выберите производителя'"
            />
          </div>
        </div>
        <div v-if="formErrors.device_model" class="alert alert-danger mb-3">
          {{ formErrors.device_model.join(', ') }}
        </div>

        <!-- SNMP Community -->
        <div class="mb-3">
          <label for="snmp_community" class="form-label">SNMP сообщество</label>
          <input
            id="snmp_community"
            v-model="formData.snmp_community"
            type="text"
            class="form-control"
            :class="{ 'is-invalid': formErrors.snmp_community }"
          />
          <div v-if="formErrors.snmp_community" class="invalid-feedback d-block">
            {{ formErrors.snmp_community.join(', ') }}
          </div>
        </div>

        <!-- MAC Address -->
        <div class="mb-3">
          <label for="mac_address" class="form-label">MAC-адрес</label>
          <input
            id="mac_address"
            v-model="formData.mac_address"
            type="text"
            class="form-control"
            :class="{ 'is-invalid': formErrors.mac_address }"
          />
          <div v-if="formErrors.mac_address" class="invalid-feedback d-block">
            {{ formErrors.mac_address.join(', ') }}
          </div>
        </div>

        <!-- Organization -->
        <div class="mb-3">
          <label for="organization" class="form-label">
            Организация <span class="text-danger">*</span>
          </label>
          <select
            id="organization"
            v-model="formData.organization"
            class="form-select"
            :class="{ 'is-invalid': formErrors.organization }"
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
          <div v-if="formErrors.organization" class="invalid-feedback d-block">
            {{ formErrors.organization.join(', ') }}
          </div>
        </div>

        <!-- SNMP Probe -->
        <div class="mb-3 p-3 bg-light rounded">
          <button
            type="button"
            class="btn btn-outline-primary w-100"
            :disabled="isProbing"
            @click="probeSNMP"
          >
            <span v-if="isProbing" class="spinner-border spinner-border-sm me-2"></span>
            <i v-else class="bi bi-broadcast"></i>
            Опросить по SNMP
          </button>
          <div
            v-if="probeMessage"
            class="mt-2 text-center small"
            :class="probeMessageClass"
          >
            {{ probeMessage }}
          </div>
          <div v-if="modelCandidates.length" class="mt-2 text-center">
            <div class="small text-muted mb-1">Несколько подходящих моделей — выберите:</div>
            <div class="d-flex flex-wrap gap-1 justify-content-center">
              <button
                v-for="cand in modelCandidates"
                :key="cand.id"
                type="button"
                class="btn btn-sm btn-outline-secondary"
                @click="selectModelCandidate(cand)"
              >
                {{ cand.label }}
              </button>
            </div>
          </div>
          <small class="text-muted d-block mt-2 text-center">
            Если SNMP community пустое — возьмём <code>public</code>
          </small>
        </div>

        <!-- Submit buttons -->
        <div class="d-flex gap-2">
          <button type="submit" class="btn btn-primary" :disabled="isSaving">
            <span v-if="isSaving" class="spinner-border spinner-border-sm me-2"></span>
            <i v-else class="bi bi-check-lg"></i>
            {{ isEdit ? 'Обновить' : 'Сохранить' }}
          </button>
          <a href="/inventory/" class="btn btn-outline-secondary">
            <i class="bi bi-x-lg"></i> Отмена
          </a>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import SearchableSelect from '../common/SearchableSelect.vue'

const props = defineProps({
  printerId: {
    type: [Number, String],
    default: null
  }
})

const appConfig = inject('appConfig', {})

// State
const formData = reactive({
  ip_address: '',
  serial_number: '',
  mac_address: '',
  device_model: '',
  manufacturer: '',
  snmp_community: '',
  organization: ''
})

const formErrors = reactive({})
const allModels = ref([])
const manufacturers = ref([])
const organizations = ref([])
const selectedManufacturer = ref('')
const isSaving = ref(false)
const isProbing = ref(false)
const probeMessage = ref('')
const probeMessageClass = ref('')
const modelCandidates = ref([])

const isEdit = computed(() => !!props.printerId)

const filteredModels = computed(() => {
  if (!selectedManufacturer.value) return []
  return allModels.value.filter(
    m => String(m.manufacturer_id) === String(selectedManufacturer.value)
  )
})

const modelOptions = computed(() =>
  filteredModels.value.map(m => ({ value: String(m.id), label: m.name }))
)

// Utility functions
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function showProbeMessage(text, isError = false) {
  probeMessage.value = text
  probeMessageClass.value = isError ? 'text-danger' : 'text-success'
  setTimeout(() => {
    probeMessage.value = ''
  }, 4000)
}

function clearFormErrors() {
  Object.keys(formErrors).forEach(key => delete formErrors[key])
}

// Load data
async function loadModelsAndOrganizations() {
  try {
    // Load models
    const modelsResp = await fetch('/inventory/api/all-printer-models/')
    const modelsData = await modelsResp.json()
    allModels.value = modelsData.models || []

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

    // Load organizations (from initial data or API)
    if (appConfig.initialData?.organizations) {
      organizations.value = appConfig.initialData.organizations
    } else {
      // Fetch from API if needed
      const orgResp = await fetch('/inventory/api/organizations/')
      const orgData = await orgResp.json()
      organizations.value = orgData.organizations || []
    }
  } catch (error) {
    console.error('Error loading data:', error)
  }
}

async function loadPrinterData() {
  if (!props.printerId) return

  try {
    const response = await fetch(`/inventory/api/printer/${props.printerId}/`)
    const data = await response.json()

    formData.ip_address = data.ip_address || ''
    formData.serial_number = data.serial_number || ''
    formData.mac_address = data.mac_address || ''
    formData.snmp_community = data.snmp_community || ''
    formData.organization = data.organization_id || ''
    formData.device_model = data.device_model_id ? String(data.device_model_id) : ''
    formData.manufacturer = data.manufacturer_id || ''

    // Set manufacturer to populate models dropdown
    if (data.manufacturer_id) {
      selectedManufacturer.value = data.manufacturer_id
    }
  } catch (error) {
    console.error('Error loading printer:', error)
    alert('Ошибка загрузки данных принтера')
  }
}

// Manufacturer change handler
function onManufacturerChange() {
  if (!selectedManufacturer.value) {
    formData.device_model = ''
  }
  formData.manufacturer = selectedManufacturer.value
}

// --- Model matching (fuzzy) ---
// Нормализация: нижний регистр, убираем разделители, схлопываем пробелы.
function normalizeModel(s) {
  return (s || '')
    .toLowerCase()
    .replace(/[-_/\\.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// Токены без пробелов — для сравнения "M2040dn" ≈ "M 2040 dn".
function compactModel(s) {
  return normalizeModel(s).replace(/\s+/g, '')
}

// Числовые серии модели (≥3 цифр) — самый различающий кусок: "2040", "3550".
function digitCores(s) {
  return normalizeModel(s).match(/\d{3,}/g) || []
}

// Канонизация производителя: HP может писаться "HP" или "Hewlett-Packard".
function canonicalMfr(s) {
  const n = normalizeModel(s)
  if (/hewlett|packard|\bhp\b/.test(n)) return 'hp'
  if (/kyocera/.test(n)) return 'kyocera'
  return n
}

// Производитель из XML и из каталога — один и тот же (с учётом сокращений)?
function mfrMatches(a, b) {
  const ca = canonicalMfr(a)
  const cb = canonicalMfr(b)
  if (!ca || !cb) return false
  return ca === cb || ca.includes(cb) || cb.includes(ca)
}

// Оценка близости 0..1 между названием из XML и названием каталога.
function scoreModel(target, candidate) {
  const t = normalizeModel(target)
  const c = normalizeModel(candidate)
  if (!t || !c) return 0
  if (t === c) return 1

  const tc = compactModel(target)
  const cc = compactModel(candidate)
  if (tc === cc) return 0.97
  if (tc.includes(cc) || cc.includes(tc)) {
    return 0.85 * (Math.min(tc.length, cc.length) / Math.max(tc.length, cc.length))
  }

  // Совпадение цифрового ядра: суффиксы dn/dw/dnf (дуплекс/факс/сеть)
  // для каталога не важны, поэтому общий номер "2040" — сильный сигнал.
  const td = digitCores(target)
  const cd = new Set(digitCores(candidate))
  if (td.some(d => cd.has(d))) return 0.8

  // Пересечение токенов (на случай перестановки/лишних слов).
  const tt = new Set(t.split(' '))
  const ct = new Set(c.split(' '))
  let shared = 0
  tt.forEach(tok => { if (ct.has(tok)) shared += 1 })
  const union = new Set([...tt, ...ct]).size
  return union ? 0.7 * (shared / union) : 0
}

// Проставляет производителя и модель по объекту каталога.
function applyModelChoice(m) {
  selectedManufacturer.value = String(m.manufacturer_id)
  formData.manufacturer = String(m.manufacturer_id)
  setTimeout(() => {
    formData.device_model = String(m.id)
  }, 150)
}

// Выбор пользователем одного из предложенных кандидатов.
function selectModelCandidate(cand) {
  const m = allModels.value.find(x => String(x.id) === String(cand.id))
  if (m) {
    applyModelChoice(m)
    showProbeMessage(`✓ Модель выбрана: ${m.name}`)
  }
  modelCandidates.value = []
}

// Подбирает модель из каталога по строкам из XML и проставляет её.
// Возвращает true, если модель выбрана автоматически.
function matchModelByName(mfrStr, modelStr) {
  modelCandidates.value = []
  const target = normalizeModel(modelStr)
  if (!target) return false

  // Ищем по всему каталогу ПО МОДЕЛИ (имя — надёжный сигнал),
  // а совпадение производителя добавляем как бонус к ранжированию
  // (вендор ненадёжен: "HP" vs "Hewlett-Packard").
  const THRESHOLD = 0.6
  const MFR_BONUS = 0.15
  const scored = allModels.value
    .map(m => {
      const base = scoreModel(modelStr, m.name)
      const rank = base + (mfrMatches(mfrStr, m.manufacturer) ? MFR_BONUS : 0)
      return { m, base, rank }
    })
    .filter(x => x.base >= THRESHOLD)
    .sort((a, b) => b.rank - a.rank)

  if (!scored.length) {
    showProbeMessage(`Модель не найдена в каталоге: «${modelStr}» — выберите вручную`, true)
    return false
  }

  // Однозначный лидер (заметно выше остальных) — ставим автоматически.
  const top = scored[0]
  const tied = scored.filter(x => top.rank - x.rank < 0.05)
  if (tied.length === 1) {
    applyModelChoice(top.m)
    showProbeMessage(`✓ Модель подобрана: ${top.m.name}`)
    return true
  }

  // Несколько равнозначных вариантов — предлагаем выбор пользователю.
  modelCandidates.value = tied.map(x => ({
    id: String(x.m.id),
    label: `${x.m.manufacturer} ${x.m.name}`
  }))
  showProbeMessage(`Найдено несколько моделей по «${modelStr}» — уточните`, true)
  return false
}

// Lookup by serial (from contracts)
async function lookupBySerial() {
  const serial = formData.serial_number.trim()
  if (!serial) return false

  try {
    const url = `/contracts/api/lookup-by-serial/?serial=${encodeURIComponent(serial)}`
    const resp = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } })

    if (!resp.headers.get('content-type')?.includes('application/json')) {
      return false
    }

    const data = await resp.json()

    if (!data.ok || !data.found) {
      return false
    }

    // Fill organization
    const orgId = String(data.device.organization?.id || '')
    if (orgId) {
      formData.organization = orgId
    }

    // Fill manufacturer and model
    let modelMatched = false
    if (data.device.manufacturer?.id && data.device.model?.id) {
      const manufacturerId = String(data.device.manufacturer.id)
      const modelId = String(data.device.model.id)

      const modelExists = allModels.value.find(m => String(m.id) === modelId)

      if (modelExists) {
        selectedManufacturer.value = manufacturerId
        formData.manufacturer = manufacturerId

        setTimeout(() => {
          formData.device_model = modelId
        }, 150)
        modelMatched = true
      }
    }

    // Fill SNMP community if empty
    if (!formData.snmp_community.trim()) {
      formData.snmp_community = 'public'
    }

    showProbeMessage('✓ Заполнено из договора')
    return modelMatched
  } catch (err) {
    console.error('Error auto-filling:', err)
    return false
  }
}

// SNMP Probe
async function probeSNMP() {
  const ip = formData.ip_address.trim()
  if (!ip) {
    showProbeMessage('Введите IP-адрес', true)
    return
  }

  let comm = formData.snmp_community.trim() || 'public'
  if (!formData.snmp_community) {
    formData.snmp_community = 'public'
  }

  isProbing.value = true
  modelCandidates.value = []
  showProbeMessage('Опрос устройства...')

  try {
    const resp = await fetch('/inventory/api/probe-serial/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ ip, community: comm })
    })

    if (!resp.headers.get('content-type')?.includes('application/json')) {
      throw new Error('Требуется авторизация')
    }

    const data = await resp.json()
    if (!data.ok) throw new Error(data.error)

    formData.serial_number = data.serial || formData.serial_number

    // MAC из XML, если поле пустое
    if (data.mac && !formData.mac_address.trim()) {
      formData.mac_address = data.mac
    }

    showProbeMessage('✓ Серийник получен: ' + data.serial)

    // Auto-lookup by serial (договор)
    const matchedFromContract = await lookupBySerial()

    // Если по договору модель не определилась — пробуем по названию из XML
    if (!matchedFromContract && data.model) {
      matchModelByName(data.manufacturer, data.model)
    }
  } catch (err) {
    showProbeMessage(err.message || 'Ошибка опроса', true)
  } finally {
    isProbing.value = false
  }
}

// Submit form
async function handleSubmit() {
  clearFormErrors()
  isSaving.value = true

  try {
    const url = isEdit.value
      ? `/inventory/${props.printerId}/edit/`
      : '/inventory/add-submit/'

    const formDataToSend = new FormData()
    Object.keys(formData).forEach(key => {
      formDataToSend.append(key, formData[key] || '')
    })

    const response = await fetch(url, {
      method: 'POST',
      body: formDataToSend,
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      }
    })

    const data = await response.json()

    if (response.ok && data.success) {
      // Redirect to printer list on success
      window.location.href = '/inventory/'
    } else {
      // Parse Django form errors
      if (data.error) {
        try {
          const errors = JSON.parse(data.error)
          Object.entries(errors).forEach(([field, msgs]) => {
            formErrors[field] = msgs.map(m => m.message)
          })
        } catch (e) {
          formErrors.__all__ = [data.error]
        }
      }
    }
  } catch (error) {
    console.error('Error saving printer:', error)
    formErrors.__all__ = ['Не удалось сохранить принтер']
  } finally {
    isSaving.value = false
  }
}

// Lifecycle
onMounted(async () => {
  await loadModelsAndOrganizations()
  if (isEdit.value) {
    await loadPrinterData()
  }
})
</script>

<style scoped>
.is-invalid {
  border-color: #dc3545;
}
</style>
