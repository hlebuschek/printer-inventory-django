<template>
  <div class="container-fluid month-changes-page">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1 class="h4">
        История изменений - {{ monthName }} {{ year }}
        <span v-if="activeFiltersText" class="badge bg-info ms-2">{{ activeFiltersText }}</span>
      </h1>
      <a href="/monthly-report/" class="btn btn-outline-secondary">
        ← К списку месяцев
      </a>
    </div>

    <!-- Фильтры -->
    <div v-if="filters.user || filters.changeType !== 'all'" class="alert alert-info">
      <strong>Активные фильтры:</strong>
      <ul class="mb-0 mt-2">
        <li v-if="filters.user">Пользователь: <strong>{{ filters.user }}</strong></li>
        <li v-if="filters.changeType === 'edited_auto'">Тип: <strong>Изменения автоматических значений</strong></li>
        <li v-if="filters.changeType === 'filled_empty'">Тип: <strong>Заполнение пустых полей</strong></li>
      </ul>
      <button class="btn btn-sm btn-outline-secondary mt-2" @click="clearFilters">
        Сбросить фильтры
      </button>
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

    <!-- Таблица изменений -->
    <div v-else class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0">Найдено изменений: {{ changes.length }}</h5>
      </div>
      <div class="card-body p-0">
        <div v-if="changes.length > 0" class="table-responsive">
          <table class="table table-hover table-sm mb-0">
            <thead class="table-light">
              <tr>
                <th style="width: 150px;">Время</th>
                <th style="width: 200px;">Пользователь</th>
                <th>Устройство</th>
                <th style="width: 150px;">Поле</th>
                <th style="width: 120px;" class="text-center">Изменение</th>
                <th style="width: 100px;">Тип</th>
                <th style="width: 120px;">IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="change in changes" :key="change.id">
                <td>
                  <div class="fw-semibold small">{{ formatDate(change.timestamp) }}</div>
                  <small class="text-muted">{{ formatTime(change.timestamp) }}</small>
                </td>
                <td>
                  <div class="fw-semibold small">{{ change.user_full_name }}</div>
                  <small class="text-muted">{{ change.user_username }}</small>
                </td>
                <td>
                  <div class="small">
                    <strong>{{ change.organization }}</strong>
                    <span v-if="change.branch"> / {{ change.branch }}</span>
                  </div>
                  <div class="text-muted small">
                    {{ change.city }}, {{ change.address }}
                  </div>
                  <div class="text-muted small">
                    {{ change.equipment_model }}
                    <span v-if="change.serial_number"> (SN: {{ change.serial_number }})</span>
                  </div>
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
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="alert alert-secondary m-3">
          Нет изменений по заданным фильтрам
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  year: {
    type: Number,
    required: true
  },
  month: {
    type: Number,
    required: true
  }
})

const changes = ref([])
const loading = ref(true)
const error = ref(null)

// Фильтры из URL
const filters = ref({
  user: null,
  changeType: 'all'
})

// Computed
const monthName = computed(() => {
  const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ]
  return monthNames[props.month - 1]
})

const activeFiltersText = computed(() => {
  const parts = []
  if (filters.value.user) parts.push(`Пользователь: ${filters.value.user}`)
  if (filters.value.changeType === 'edited_auto') parts.push('Редакт. авто')
  if (filters.value.changeType === 'filled_empty') parts.push('Заполнение')
  return parts.join(', ')
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

    const url = `/monthly-report/api/month-changes/${props.year}/${props.month}/?${params.toString()}`
    const response = await fetch(url)
    const data = await response.json()

    if (data.ok) {
      changes.value = data.changes
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
  filters.value.user = null
  filters.value.changeType = 'all'
  // Обновляем URL
  window.history.replaceState({}, '', `/monthly-report/month-changes/${props.year}/${props.month}/`)
  loadChanges()
}

// Загружаем фильтры из URL
function loadFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search)
  filters.value.user = params.get('filter_user')
  filters.value.changeType = params.get('filter_change_type') || 'all'
}

onMounted(() => {
  loadFiltersFromUrl()
  loadChanges()
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
</style>
