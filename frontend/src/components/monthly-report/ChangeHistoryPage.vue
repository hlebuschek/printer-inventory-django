<template>
  <div class="container-fluid">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1 class="h4">История изменений</h1>
      <a :href="`/monthly-report/${monthStr}/`" class="btn btn-outline-secondary">
        ← Вернуться к отчету
      </a>
    </div>

    <!-- Информация о записи -->
    <div class="card mb-4">
      <div class="card-header">
        <h5 class="mb-0">Информация о записи</h5>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="col-md-6">
            <strong>Организация:</strong> {{ report.organization }}<br>
            <strong>Филиал:</strong> {{ report.branch }}<br>
            <strong>Город:</strong> {{ report.city }}<br>
            <strong>Адрес:</strong> {{ report.address }}
          </div>
          <div class="col-md-6">
            <strong>Модель:</strong> {{ report.equipment_model }}<br>
            <strong>Серийный номер:</strong> {{ report.serial_number }}<br>
            <strong>Инв. номер:</strong> {{ report.inventory_number }}<br>
            <strong>Месяц:</strong> {{ monthName }}
          </div>
        </div>
      </div>
    </div>

    <!-- Текущие значения -->
    <div class="card mb-4">
      <div class="card-header">
        <h5 class="mb-0">Текущие значения счетчиков</h5>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="col-md-3">
            <h6>A4 Ч/Б</h6>
            <div>Начало: <strong>{{ report.a4_bw_start || 0 }}</strong></div>
            <div>Конец: <strong>{{ report.a4_bw_end || 0 }}</strong></div>
            <small v-if="report.a4_bw_end_auto" class="text-muted">
              Авто: {{ report.a4_bw_end_auto }}
            </small>
          </div>
          <div class="col-md-3">
            <h6>A4 Цвет</h6>
            <div>Начало: <strong>{{ report.a4_color_start || 0 }}</strong></div>
            <div>Конец: <strong>{{ report.a4_color_end || 0 }}</strong></div>
            <small v-if="report.a4_color_end_auto" class="text-muted">
              Авто: {{ report.a4_color_end_auto }}
            </small>
          </div>
          <div class="col-md-3">
            <h6>A3 Ч/Б</h6>
            <div>Начало: <strong>{{ report.a3_bw_start || 0 }}</strong></div>
            <div>Конец: <strong>{{ report.a3_bw_end || 0 }}</strong></div>
            <small v-if="report.a3_bw_end_auto" class="text-muted">
              Авто: {{ report.a3_bw_end_auto }}
            </small>
          </div>
          <div class="col-md-3">
            <h6>A3 Цвет</h6>
            <div>Начало: <strong>{{ report.a3_color_start || 0 }}</strong></div>
            <div>Конец: <strong>{{ report.a3_color_end || 0 }}</strong></div>
            <small v-if="report.a3_color_end_auto" class="text-muted">
              Авто: {{ report.a3_color_end_auto }}
            </small>
          </div>
        </div>
        <div class="mt-3">
          <h6>
            Итого отпечатков:
            <span class="badge bg-primary fs-6">{{ report.total_prints || 0 }}</span>
          </h6>
        </div>
      </div>
    </div>

    <!-- История изменений -->
    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0">История изменений ({{ history.length }})</h5>
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-secondary" @click="exportHistory">
            📄 Экспорт
          </button>
          <button class="btn btn-outline-secondary" @click="filterHistory">
            🔍 Фильтр
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div v-if="history.length > 0" class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>Время</th>
                <th>Пользователь</th>
                <th>Поле</th>
                <th>Изменение</th>
                <th>Источник</th>
                <th>IP</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="change in history" :key="change.id">
                <tr :data-change-id="change.id">
                  <td>
                    <div class="fw-semibold">{{ formatDate(change.timestamp) }}</div>
                    <small class="text-muted">{{ timeAgo(change.timestamp) }} назад</small>
                  </td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <div>
                        <div class="fw-semibold">
                          {{ change.user_full_name || change.user_username }}
                        </div>
                        <small class="text-muted">{{ change.user_username }}</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span class="badge bg-secondary">{{ change.field_display }}</span>
                  </td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <span v-if="change.old_value !== null" class="text-danger fw-semibold">
                        {{ change.old_value }}
                      </span>
                      <span v-else class="text-muted">—</span>

                      <span class="text-muted">→</span>

                      <span v-if="change.new_value !== null" class="text-success fw-semibold">
                        {{ change.new_value }}
                      </span>
                      <span v-else class="text-muted">—</span>

                      <span
                        v-if="change.change_delta"
                        class="badge ms-1"
                        :class="change.change_delta > 0 ? 'bg-success' : 'bg-danger'"
                      >
                        {{ change.change_delta > 0 ? '+' : '' }}{{ change.change_delta }}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span
                      class="badge"
                      :class="{
                        'bg-primary': change.change_source === 'manual',
                        'bg-info': change.change_source === 'auto_sync',
                        'bg-warning': change.change_source === 'excel_upload',
                        'bg-secondary': !['manual', 'auto_sync', 'excel_upload'].includes(change.change_source)
                      }"
                    >
                      {{ getSourceLabel(change.change_source) }}
                    </span>
                  </td>
                  <td>
                    <code v-if="change.ip_address" class="small">{{ change.ip_address }}</code>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <button
                      v-if="change.old_value !== null && change.change_source === 'manual'"
                      class="btn btn-sm btn-outline-warning"
                      @click="openRevertModal(change)"
                      title="Откатить изменение"
                    >
                      ↶ Откат
                    </button>
                  </td>
                </tr>
                <tr v-if="change.comment" class="table-light">
                  <td colspan="7">
                    <small class="text-muted">
                      <strong>Комментарий:</strong> {{ change.comment }}
                    </small>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div v-else class="text-center py-5 text-muted">
          <div class="fs-1 mb-3">📝</div>
          <h5>История изменений пуста</h5>
          <p>Для этой записи еще не было зафиксировано изменений счетчиков.</p>
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
              <strong>Поле:</strong> {{ selectedChange.field_display }}<br>
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
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  reportId: {
    type: Number,
    required: true
  }
})

const report = ref({})
const history = ref([])
const selectedChange = ref(null)
const reverting = ref(false)
const revertModalRef = ref(null)
let revertModalInstance = null

const monthStr = computed(() => {
  if (!report.value.month) return ''
  return report.value.month
})

const monthName = computed(() => {
  if (!report.value.month) return ''
  const [year, month] = report.value.month.split('-')
  const date = new Date(year, parseInt(month) - 1)
  return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long' })
})

// Load data
async function loadData() {
  try {
    const response = await fetch(`/monthly-report/api/change-history/${props.reportId}/`)
    const data = await response.json()

    if (data.ok) {
      report.value = data.report
      history.value = data.history
    }
  } catch (error) {
    console.error('Error loading change history:', error)
  }
}

// Format date
function formatDate(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// Time ago
function timeAgo(timestamp) {
  const now = new Date()
  const past = new Date(timestamp)
  const diffMs = now - past
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'менее минуты'
  if (diffMins < 60) return `${diffMins} мин.`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} ч.`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays} дн.`

  const diffMonths = Math.floor(diffDays / 30)
  return `${diffMonths} мес.`
}

// Get source label
function getSourceLabel(source) {
  const labels = {
    manual: 'Ручное',
    auto_sync: 'Автосинк',
    excel_upload: 'Excel'
  }
  return labels[source] || source
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
      // Reload data
      await loadData()
    } else {
      alert('Ошибка отката: ' + data.error)
    }
  } catch (error) {
    alert('Ошибка: ' + error.message)
  } finally {
    reverting.value = false
  }
}

// Export history
function exportHistory() {
  window.open(`/monthly-report/api/export-history/${props.reportId}/`, '_blank')
}

// Filter history
function filterHistory() {
  alert('Функция фильтрации будет добавлена в следующей версии')
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
  await loadData()

  // Initialize Bootstrap modal (используем глобальный объект bootstrap)
  if (revertModalRef.value && window.bootstrap) {
    revertModalInstance = new window.bootstrap.Modal(revertModalRef.value)
  }
})
</script>

<style scoped>
.table th {
  font-weight: 600;
  white-space: nowrap;
}

.table td {
  vertical-align: middle;
}
</style>
