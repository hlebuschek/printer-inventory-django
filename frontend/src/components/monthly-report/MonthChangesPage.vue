<template>
  <div class="container-fluid month-changes-page">
    <!-- Toast Container -->
    <ToastContainer />

    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1 class="h4">
        История изменений - {{ monthName }} {{ year }}
        <span v-if="activeFiltersText" class="badge bg-info ms-2">{{ activeFiltersText }}</span>
      </h1>
      <a href="/monthly-report/" class="btn btn-outline-secondary">
        ← К списку месяцев
      </a>
    </div>

    <!-- Панель фильтров -->
    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-md-3">
            <label class="form-label small fw-semibold">Пользователь</label>
            <select v-model="filters.user" class="form-select form-select-sm" @change="applyFilters">
              <option value="">Все пользователи</option>
              <option v-for="user in availableUsers" :key="user" :value="user">
                {{ user }}
              </option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small fw-semibold">Тип изменений</label>
            <select v-model="filters.changeType" class="form-select form-select-sm" @change="applyFilters">
              <option value="all">Все изменения</option>
              <option value="edited_auto">Редактирование автоматики</option>
              <option value="filled_empty">Заполнение пустых</option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small fw-semibold">Устройство (серийник)</label>
            <input
              v-model="filters.deviceSerial"
              type="text"
              class="form-control form-control-sm"
              placeholder="Введите серийный номер..."
              list="device-serial-list"
              @input="debouncedApplyFilters"
            />
            <datalist id="device-serial-list">
              <option v-for="device in filteredDevices" :key="device.serial" :value="device.serial">
                {{ device.model }} ({{ device.serial }})
              </option>
            </datalist>
          </div>
          <div class="col-md-3">
            <button class="btn btn-sm btn-outline-secondary w-100" @click="clearFilters">
              <i class="bi bi-x-circle"></i> Сбросить фильтры
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Информация о устройстве (когда выбран фильтр по устройству) -->
    <div v-if="filters.deviceSerial && currentDeviceReport" class="card mb-4">
      <div class="card-header">
        <h5 class="mb-0">Информация о записи</h5>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="col-md-6">
            <strong>Организация:</strong> {{ currentDeviceReport.organization }}<br>
            <strong>Филиал:</strong> {{ currentDeviceReport.branch || '—' }}<br>
            <strong>Город:</strong> {{ currentDeviceReport.city }}<br>
            <strong>Адрес:</strong> {{ currentDeviceReport.address }}
          </div>
          <div class="col-md-6">
            <strong>Модель:</strong> {{ currentDeviceReport.equipment_model }}<br>
            <strong>Серийный номер:</strong> {{ currentDeviceReport.serial_number }}<br>
            <strong>Инв. номер:</strong> {{ currentDeviceReport.inventory_number || '—' }}
          </div>
        </div>

        <!-- Текущие значения счетчиков -->
        <div v-if="currentDeviceReport.counters" class="mt-3">
          <h6>Текущие значения счетчиков</h6>
          <div class="row">
            <div class="col-md-3">
              <strong>A4 Ч/Б</strong>
              <div>Начало: <strong>{{ currentDeviceReport.counters.a4_bw_start || 0 }}</strong></div>
              <div>Конец: <strong>{{ currentDeviceReport.counters.a4_bw_end || 0 }}</strong></div>
              <small v-if="currentDeviceReport.counters.a4_bw_end_auto" class="text-muted">
                Авто: {{ currentDeviceReport.counters.a4_bw_end_auto }}
              </small>
            </div>
            <div class="col-md-3">
              <strong>A4 Цвет</strong>
              <div>Начало: <strong>{{ currentDeviceReport.counters.a4_color_start || 0 }}</strong></div>
              <div>Конец: <strong>{{ currentDeviceReport.counters.a4_color_end || 0 }}</strong></div>
              <small v-if="currentDeviceReport.counters.a4_color_end_auto" class="text-muted">
                Авто: {{ currentDeviceReport.counters.a4_color_end_auto }}
              </small>
            </div>
            <div class="col-md-3">
              <strong>A3 Ч/Б</strong>
              <div>Начало: <strong>{{ currentDeviceReport.counters.a3_bw_start || 0 }}</strong></div>
              <div>Конец: <strong>{{ currentDeviceReport.counters.a3_bw_end || 0 }}</strong></div>
              <small v-if="currentDeviceReport.counters.a3_bw_end_auto" class="text-muted">
                Авто: {{ currentDeviceReport.counters.a3_bw_end_auto }}
              </small>
            </div>
            <div class="col-md-3">
              <strong>A3 Цвет</strong>
              <div>Начало: <strong>{{ currentDeviceReport.counters.a3_color_start || 0 }}</strong></div>
              <div>Конец: <strong>{{ currentDeviceReport.counters.a3_color_end || 0 }}</strong></div>
              <small v-if="currentDeviceReport.counters.a3_color_end_auto" class="text-muted">
                Авто: {{ currentDeviceReport.counters.a3_color_end_auto }}
              </small>
            </div>
          </div>
        </div>

        <!-- Кнопка возврата на автоопрос -->
        <div v-if="hasManualFlags" class="mt-4 p-3 border border-warning rounded bg-light">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>
              <strong>Принтер заблокирован для автоопроса</strong>
              <p class="mb-0 mt-2 text-muted small">
                Один или несколько счетчиков были изменены вручную и больше не обновляются автоматически.
                Нажмите кнопку справа, чтобы вернуть принтер на автоматический опрос.
              </p>
            </div>
            <button
              v-if="permissions.can_reset_auto_polling"
              class="btn btn-warning"
              @click="resetAllManualFlags"
              :disabled="isResetting"
            >
              <span v-if="isResetting" class="spinner-border spinner-border-sm me-2"></span>
              <i v-else class="bi bi-arrow-clockwise me-2"></i>
              Вернуть на автоопрос
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Загрузка -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <!-- Ошибка -->
    <div v-else-if="error" class="alert alert-danger">
      <i class="bi bi-exclamation-triangle"></i>
      {{ error }}
    </div>

    <!-- Группы изменений -->
    <div v-else>
      <div class="mb-3">
        <div class="d-flex justify-content-between align-items-center">
          <h5 class="mb-0">
            Найдено: {{ totalChanges }} изменений в {{ groups.length }} устройствах
          </h5>
          <div class="btn-group btn-group-sm">
            <button
              class="btn btn-outline-secondary"
              @click="expandAll"
            >
              <i class="bi bi-arrows-expand"></i> Развернуть все
            </button>
            <button
              class="btn btn-outline-secondary"
              @click="collapseAll"
            >
              <i class="bi bi-arrows-collapse"></i> Свернуть все
            </button>
          </div>
        </div>
      </div>

      <div v-if="groups.length === 0" class="alert alert-secondary">
        Нет изменений по заданным фильтрам
      </div>

      <!-- Аккордеон с группами -->
      <div class="accordion" id="changesAccordion">
        <div
          v-for="(group, index) in groups"
          :key="index"
          class="accordion-item"
        >
          <h2 class="accordion-header">
            <button
              class="accordion-button"
              :class="{ collapsed: !expandedGroups[index] }"
              type="button"
              @click="toggleGroup(index)"
            >
              <div class="w-100 d-flex justify-content-between align-items-center pe-3">
                <div>
                  <strong>{{ group.device_info.equipment_model }}</strong>
                  <span class="text-muted ms-2">SN: {{ group.device_info.serial_number }}</span>
                  <br>
                  <small class="text-muted">
                    {{ group.device_info.organization }}
                    <span v-if="group.device_info.branch"> / {{ group.device_info.branch }}</span>
                    — {{ group.device_info.city }}, {{ group.device_info.address }}
                  </small>
                </div>
                <span class="badge bg-primary-subtle text-primary-emphasis fs-6">
                  {{ group.changes_count }} {{ getChangesLabel(group.changes_count) }}
                </span>
              </div>
            </button>
          </h2>
          <div
            class="accordion-collapse collapse"
            :class="{ show: expandedGroups[index] }"
          >
            <div class="accordion-body p-0">
              <div class="table-responsive">
                <table class="table table-hover table-sm mb-0">
                  <thead class="table-light">
                    <tr>
                      <th style="width: 150px;">Время</th>
                      <th style="width: 200px;">Пользователь</th>
                      <th style="width: 150px;">Поле</th>
                      <th style="width: 120px;" class="text-center">Изменение</th>
                      <th style="width: 100px;">Тип</th>
                      <th style="width: 120px;">IP</th>
                      <th style="width: 100px;">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="change in group.changes" :key="change.id">
                      <td>
                        <div class="fw-semibold small">{{ formatDate(change.timestamp) }}</div>
                        <small class="text-muted">{{ formatTime(change.timestamp) }}</small>
                      </td>
                      <td>
                        <div class="fw-semibold small">{{ change.user_full_name }}</div>
                        <small class="text-muted">{{ change.user_username }}</small>
                      </td>
                      <td>
                        <span class="badge bg-secondary-subtle text-secondary-emphasis">
                          {{ change.field_label }}
                        </span>
                      </td>
                      <td class="text-center">
                        <div class="d-flex align-items-center justify-content-center gap-1">
                          <span class="badge bg-light text-dark">{{ change.old_value || 0 }}</span>
                          <i class="bi bi-arrow-right"></i>
                          <span class="badge bg-primary">{{ change.new_value }}</span>
                        </div>
                      </td>
                      <td>
                        <span
                          v-if="change.change_type === 'edited_auto'"
                          class="badge bg-warning-subtle text-warning-emphasis"
                          title="Изменение автоматического значения"
                        >
                          <i class="bi bi-pencil-square"></i> Отред.
                        </span>
                        <span
                          v-else
                          class="badge bg-info-subtle text-info-emphasis"
                          title="Заполнение пустого поля"
                        >
                          <i class="bi bi-plus-circle"></i> Заполн.
                        </span>
                      </td>
                      <td>
                        <small class="text-muted">{{ change.ip_address || '—' }}</small>
                      </td>
                      <td>
                        <button
                          v-if="change.old_value !== null && change.change_source === 'manual' && permissions.can_reset_auto_polling"
                          class="btn btn-sm btn-outline-warning"
                          @click="openRevertModal(change)"
                          title="Откатить изменение"
                        >
                          ↶ Откат
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Модалка подтверждения отката -->
    <div
      ref="revertModalRef"
      class="modal fade"
      tabindex="-1"
      aria-labelledby="revertModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 id="revertModalLabel" class="modal-title">Подтверждение отката</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <p>Вы уверены, что хотите откатить это изменение?</p>
            <div v-if="selectedChange" class="bg-light p-3 rounded">
              <strong>Пользователь:</strong> {{ selectedChange.user_full_name || selectedChange.user_username }}<br>
              <strong>Поле:</strong> {{ selectedChange.field_label }}<br>
              <strong>Восстановить значение:</strong>
              <span class="text-success fw-bold">{{ selectedChange.old_value }}</span><br>
              <strong>Текущее значение:</strong>
              <span class="text-danger">{{ selectedChange.new_value }}</span>
            </div>
            <div class="alert alert-warning mt-3">
              <strong>Внимание:</strong> Откат создаст новую запись в истории изменений.
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              Отмена
            </button>
            <button
              type="button"
              class="btn btn-warning"
              @click="confirmRevert"
              :disabled="reverting"
            >
              {{ reverting ? 'Откатываем...' : 'Откатить' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { useToast } from '../../composables/useToast'
import ToastContainer from '../common/ToastContainer.vue'

const { showToast } = useToast()

const props = defineProps({
  year: {
    type: Number,
    required: true
  },
  month: {
    type: Number,
    required: true
  },
  permissions: {
    type: Object,
    default: () => ({})
  }
})

const groups = ref([])
const totalChanges = ref(0)
const loading = ref(true)
const error = ref(null)
const expandedGroups = reactive({})

// Списки для фильтров
const availableUsers = ref([])
const availableDevices = ref([])

// Фильтры из URL
const filters = ref({
  user: '',
  changeType: 'all',
  deviceSerial: ''  // Фильтр по серийному номеру устройства
})

// Данные для устройства (когда выбран фильтр по одному устройству)
const currentDeviceReport = ref(null)

// Для отката изменений
const selectedChange = ref(null)
const reverting = ref(false)
const revertModalRef = ref(null)
const isResetting = ref(false)
let revertModalInstance = null
let debounceTimeout = null

// Computed
const monthName = computed(() => {
  const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ]
  return monthNames[props.month - 1]
})

const hasActiveFilters = computed(() => {
  return filters.value.user || filters.value.changeType !== 'all' || filters.value.deviceSerial
})

const activeFiltersText = computed(() => {
  const parts = []
  if (filters.value.user) parts.push(`Пользователь: ${filters.value.user}`)
  if (filters.value.changeType === 'edited_auto') parts.push('Редакт. авто')
  if (filters.value.changeType === 'filled_empty') parts.push('Заполнение')
  if (filters.value.deviceSerial) parts.push(`Устройство: ${filters.value.deviceSerial}`)
  return parts.join(', ')
})

// Проверка наличия флагов ручного редактирования
const hasManualFlags = computed(() => {
  if (!currentDeviceReport.value || !currentDeviceReport.value.counters) return false
  return currentDeviceReport.value.counters.a4_bw_end_manual ||
         currentDeviceReport.value.counters.a4_color_end_manual ||
         currentDeviceReport.value.counters.a3_bw_end_manual ||
         currentDeviceReport.value.counters.a3_color_end_manual
})

// Фильтрация устройств на стороне клиента
const filteredDevices = computed(() => {
  if (!filters.value.deviceSerial || filters.value.deviceSerial.length < 1) {
    return availableDevices.value
  }

  const search = filters.value.deviceSerial.toLowerCase()
  return availableDevices.value.filter(device => {
    return device.serial.toLowerCase().includes(search) ||
           device.model.toLowerCase().includes(search)
  })
})

// Functions
async function loadChanges() {
  loading.value = true
  error.value = null

  try {
    const params = new URLSearchParams()
    if (filters.value.user) {
      params.append('filter_user', filters.value.user)
    }
    if (filters.value.changeType !== 'all') {
      params.append('filter_change_type', filters.value.changeType)
    }
    if (filters.value.deviceSerial) {
      params.append('filter_device_serial', filters.value.deviceSerial)
    }

    const url = `/monthly-report/api/month-changes/${props.year}/${props.month}/?${params.toString()}`
    const response = await fetch(url)
    const data = await response.json()

    if (data.ok) {
      groups.value = data.groups || []
      totalChanges.value = data.total_changes || 0

      // Собираем уникальные списки для фильтров
      const usersSet = new Set()
      const devicesMap = new Map()

      groups.value.forEach(group => {
        // Собираем устройства
        const serial = group.device_info.serial_number
        const model = group.device_info.equipment_model
        if (!devicesMap.has(serial)) {
          devicesMap.set(serial, { serial, model })
        }

        // Собираем пользователей из изменений
        group.changes.forEach(change => {
          if (change.user_username) {
            usersSet.add(change.user_username)
          }
        })
      })

      availableDevices.value = Array.from(devicesMap.values()).sort((a, b) =>
        a.model.localeCompare(b.model)
      )
      availableUsers.value = Array.from(usersSet).sort()

      // Логика раскрытия групп
      if (filters.value.deviceSerial) {
        // Если есть фильтр по устройству - открываем только эту группу
        groups.value.forEach((group, index) => {
          expandedGroups[index] = group.device_info.serial_number === filters.value.deviceSerial
        })
      } else {
        // Иначе разворачиваем первые 3 группы
        groups.value.forEach((_, index) => {
          expandedGroups[index] = index < 3
        })
      }
    } else {
      error.value = data.error || 'Ошибка загрузки данных'
    }
  } catch (err) {
    console.error('Error loading changes:', err)
    error.value = 'Не удалось загрузить изменения'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  // Обновляем URL с параметрами фильтров
  const params = new URLSearchParams()
  if (filters.value.user) params.append('filter_user', filters.value.user)
  if (filters.value.changeType !== 'all') params.append('filter_change_type', filters.value.changeType)
  if (filters.value.deviceSerial) params.append('filter_device_serial', filters.value.deviceSerial)

  const newUrl = `/monthly-report/month-changes/${props.year}/${props.month}/${params.toString() ? '?' + params.toString() : ''}`
  window.history.pushState({}, '', newUrl)

  loadChanges()
  loadDeviceReport()
}

// Debounced версия для input события
function debouncedApplyFilters() {
  if (debounceTimeout) {
    clearTimeout(debounceTimeout)
  }
  debounceTimeout = setTimeout(() => {
    applyFilters()
  }, 500) // 500ms задержка после последнего ввода
}

function toggleGroup(index) {
  expandedGroups[index] = !expandedGroups[index]
}

function expandAll() {
  groups.value.forEach((_, index) => {
    expandedGroups[index] = true
  })
}

function collapseAll() {
  groups.value.forEach((_, index) => {
    expandedGroups[index] = false
  })
}

function getChangesLabel(count) {
  const lastDigit = count % 10
  const lastTwoDigits = count % 100

  if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
    return 'изменений'
  }

  if (lastDigit === 1) {
    return 'изменение'
  }

  if (lastDigit >= 2 && lastDigit <= 4) {
    return 'изменения'
  }

  return 'изменений'
}

function formatDate(timestamp) {
  const date = new Date(timestamp)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = date.getFullYear()
  return `${day}.${month}.${year}`
}

function formatTime(timestamp) {
  const date = new Date(timestamp)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

function clearFilters() {
  filters.value.user = ''
  filters.value.changeType = 'all'
  filters.value.deviceSerial = ''
  // Обновляем URL
  window.history.pushState({}, '', `/monthly-report/month-changes/${props.year}/${props.month}/`)
  loadChanges()
}

// Загружаем фильтры из URL
function loadFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search)
  filters.value.user = params.get('filter_user')
  filters.value.changeType = params.get('filter_change_type') || 'all'
  filters.value.deviceSerial = params.get('filter_device_serial') || params.get('device_serial')
}

// Загрузка данных о конкретном устройстве
async function loadDeviceReport() {
  if (!filters.value.deviceSerial) {
    currentDeviceReport.value = null
    return
  }

  try {
    const response = await fetch(
      `/monthly-report/api/device-report/${props.year}/${props.month}/${filters.value.deviceSerial}/`
    )
    const data = await response.json()

    if (data.ok) {
      currentDeviceReport.value = data.report
    } else {
      currentDeviceReport.value = null
    }
  } catch (error) {
    console.error('Error loading device report:', error)
    currentDeviceReport.value = null
  }
}

// Open revert modal
function openRevertModal(change) {
  selectedChange.value = change
  if (revertModalInstance) {
    revertModalInstance.show()
  }
}

// Confirm revert
async function confirmRevert() {
  if (!selectedChange.value) return

  reverting.value = true

  try {
    const response = await fetch(`/monthly-report/api/revert-change/${selectedChange.value.id}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (data.ok) {
      if (revertModalInstance) {
        revertModalInstance.hide()
      }
      showToast('Успешно', 'Изменение откачено', 'success')
      // Reload data
      await loadChanges()
      await loadDeviceReport()
    } else {
      showToast('Ошибка', data.error || 'Не удалось откатить изменение', 'error')
    }
  } catch (error) {
    showToast('Ошибка', 'Не удалось откатить изменение', 'error')
  } finally {
    reverting.value = false
  }
}

// Reset all manual flags - return to auto polling
async function resetAllManualFlags() {
  if (!currentDeviceReport.value || !currentDeviceReport.value.id) {
    showToast('Ошибка', 'Не найден ID отчета', 'error')
    return
  }

  if (!confirm('Вернуть принтер на автоматический опрос?\n\nВсе счетчики будут обновляться автоматически при следующей синхронизации.')) {
    return
  }

  isResetting.value = true

  try {
    const response = await fetch('/monthly-report/api/reset-all-manual-flags/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        report_id: currentDeviceReport.value.id
      })
    })

    const data = await response.json()

    if (data.success) {
      showToast(
        'Успешно',
        data.message || 'Принтер возвращен на автоматический опрос',
        'success'
      )

      // Перезагружаем данные
      await loadDeviceReport()
      await loadChanges()
    } else {
      showToast(
        'Ошибка',
        data.error || 'Неизвестная ошибка',
        'error'
      )
    }
  } catch (error) {
    console.error('Error resetting manual flags:', error)
    showToast(
      'Ошибка',
      'Не удалось сбросить флаги ручного редактирования',
      'error'
    )
  } finally {
    isResetting.value = false
  }
}

// Get CSRF token
function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

onMounted(async () => {
  loadFiltersFromUrl()
  await loadChanges()
  await loadDeviceReport()

  // Initialize Bootstrap modal (используем глобальный объект bootstrap)
  if (revertModalRef.value && window.bootstrap) {
    revertModalInstance = new window.bootstrap.Modal(revertModalRef.value)
  }
})
</script>

<style scoped>
.month-changes-page {
  padding-top: 1rem;
}

.table td {
  vertical-align: middle;
}

.table small {
  font-size: 0.8rem;
}

/* Стили для аккордеона */
.accordion-button {
  padding: 1rem 1.25rem;
}

.accordion-button:not(.collapsed) {
  background-color: #f8f9fa;
  color: #212529;
  box-shadow: none;
}

.accordion-button:focus {
  box-shadow: none;
  border-color: rgba(0,0,0,.125);
}

.accordion-item {
  margin-bottom: 0.5rem;
  border-radius: 0.375rem !important;
  border: 1px solid rgba(0,0,0,.125);
}

.accordion-button::after {
  margin-left: 0;
}
</style>
