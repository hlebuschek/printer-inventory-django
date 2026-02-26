<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-clock-history text-primary"></i>
      <span class="fw-semibold">Последние опросы</span>
      <span v-if="liveUpdated" class="badge bg-success-subtle text-success ms-auto small">
        <i class="bi bi-circle-fill" style="font-size:.5rem"></i> Live
      </span>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:320px;">
      <!-- Спиннер только при первой загрузке -->
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-muted small p-3 text-center">Нет данных</div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>Время</th>
            <th>IP</th>
            <th>Модель</th>
            <th>Организация</th>
            <th>Статус</th>
          </tr>
        </thead>
        <!-- TransitionGroup для плавного появления новых строк -->
        <TransitionGroup tag="tbody" name="row-fade">
          <tr v-for="item in data" :key="item.task_id">
            <td class="text-nowrap text-muted small">{{ formatTime(item.timestamp) }}</td>
            <td class="font-monospace small">{{ item.ip_address }}</td>
            <td class="text-truncate" style="max-width:120px;" :title="item.model">{{ item.model || '—' }}</td>
            <td class="text-truncate" style="max-width:100px;" :title="item.organization">{{ item.organization }}</td>
            <td>
              <span class="badge" :class="STATUS_BADGE[item.status] || 'bg-secondary'">
                {{ STATUS_LABEL[item.status] || item.status }}
              </span>
            </td>
          </tr>
        </TransitionGroup>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { fetchApi } from '../../../utils/api.js'

const props = defineProps({
  orgId: { type: Number, default: null },
  refreshTick: { type: Number, default: 0 },
})

const loading = ref(true)   // true только до первой успешной загрузки
const initialized = ref(false)
const error = ref(null)
const data = ref([])
const liveUpdated = ref(false)

const STATUS_BADGE = {
  SUCCESS: 'bg-success',
  FAILED: 'bg-danger',
  VALIDATION_ERROR: 'bg-warning text-dark',
  HISTORICAL_INCONSISTENCY: 'bg-secondary',
}
const STATUS_LABEL = {
  SUCCESS: 'OK',
  FAILED: 'Ошибка',
  VALIDATION_ERROR: 'Валидация',
  HISTORICAL_INCONSISTENCY: 'Расхожд.',
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function load() {
  // Спиннер только при первом открытии — при фоновых обновлениях не мигаем
  if (!initialized.value) loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({ limit: 20 })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/recent-activity/?${params}`)
    if (res.ok) {
      data.value = res.data
      initialized.value = true
    } else {
      error.value = res.error || 'Ошибка загрузки'
    }
  } catch (e) {
    error.value = 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

watch([() => props.orgId, () => props.refreshTick], () => {
  // При смене фильтров — сбрасываем, чтобы показать спиннер на новые данные
  initialized.value = false
  load()
}, { immediate: true })

defineExpose({
  load,
  markLive() { liveUpdated.value = true; setTimeout(() => { liveUpdated.value = false }, 5000) },
})
</script>

<style scoped>
/* Плавное появление новых строк при live-обновлении */
.row-fade-enter-active {
  transition: opacity 0.35s ease, background-color 0.6s ease;
}
.row-fade-enter-from {
  opacity: 0;
  background-color: rgba(25, 135, 84, 0.15);
}
.row-fade-leave-active {
  transition: opacity 0.2s ease;
  position: absolute;
}
.row-fade-leave-to {
  opacity: 0;
}
</style>
