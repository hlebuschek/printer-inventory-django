<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-cloud-check text-info"></i>
      <span class="fw-semibold">Найдены в GLPI</span>
      <span v-if="summary.total" class="badge bg-info-subtle text-info-emphasis ms-1">
        {{ summary.total }}
      </span>
      <div class="ms-auto d-flex align-items-center gap-2">
        <small v-if="summary.last_checked" class="text-muted">
          {{ formatRelative(summary.last_checked) }}
        </small>
        <button
          class="btn btn-sm btn-outline-secondary"
          title="Обновить данные из GLPI"
          :disabled="refreshing"
          @click="triggerRefresh"
        >
          <i class="bi" :class="refreshing ? 'bi-hourglass-split' : 'bi-arrow-clockwise'"></i>
        </button>
      </div>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:350px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-muted small p-3 text-center">
        <i class="bi bi-check-circle text-success"></i> Нет устройств, опрашиваемых только в GLPI
      </div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>Категория</th>
            <th>Серийник</th>
            <th>IP</th>
            <th>Организация</th>
            <th>Имя в GLPI</th>
            <th class="text-end">Счётчик GLPI</th>
            <th>Обновлено в GLPI</th>
            <th>Статус GLPI</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in data" :key="item.id">
            <td>
              <span
                class="badge"
                :class="item.category === 'OFFLINE' ? 'bg-warning-subtle text-warning-emphasis' : 'bg-info-subtle text-info-emphasis'"
              >
                {{ item.category_display }}
              </span>
            </td>
            <td class="font-monospace small">{{ item.serial_number }}</td>
            <td class="font-monospace small">{{ item.ip_address || '—' }}</td>
            <td class="text-truncate" style="max-width:120px;" :title="item.organization">
              {{ item.organization || '—' }}
            </td>
            <td class="text-truncate" style="max-width:140px;" :title="item.glpi_name">
              {{ item.glpi_name || '—' }}
            </td>
            <td class="text-end fw-semibold">
              {{ item.glpi_last_pages_counter != null ? item.glpi_last_pages_counter.toLocaleString() : '—' }}
            </td>
            <td class="small">
              {{ item.glpi_date_mod ? formatRelative(item.glpi_date_mod) : '—' }}
            </td>
            <td class="small">{{ item.glpi_state_name || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="summary.total" class="card-footer small text-muted d-flex gap-3">
      <span>
        <i class="bi bi-wifi-off text-warning"></i>
        Офлайн: {{ summary.offline_count }}
      </span>
      <span>
        <i class="bi bi-slash-circle text-info"></i>
        Не опрашиваются: {{ summary.unpolled_count }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { fetchApi } from '../../../utils/api.js'
import { useWidgetLoader } from '../../../composables/useWidgetLoader.js'

const props = defineProps({
  orgId: { type: Number, default: null },
  refreshTick: { type: Number, default: 0 },
})

const { loading, error, initialized, execute, reset } = useWidgetLoader()
const data = ref([])
const summary = ref({ total: 0, offline_count: 0, unpolled_count: 0, last_checked: null })
const refreshing = ref(false)

async function load() {
  await execute(async () => {
    const params = new URLSearchParams()
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/glpi-cross-check/?${params}`)
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data.items || []
    summary.value = res.data.summary || { total: 0, offline_count: 0, unpolled_count: 0, last_checked: null }
  })
}

async function triggerRefresh() {
  refreshing.value = true
  try {
    const res = await fetchApi('/dashboard/api/glpi-cross-check/refresh/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
    })
    if (res.ok) {
      // Перезагрузим данные через 5 секунд (задача запущена в фоне)
      setTimeout(() => {
        load()
        refreshing.value = false
      }, 5000)
    } else {
      refreshing.value = false
    }
  } catch {
    refreshing.value = false
  }
}

function getCsrfToken() {
  const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='))
  return cookie ? cookie.split('=')[1] : ''
}

function formatRelative(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return 'только что'
  if (diffMin < 60) return `${diffMin} мин. назад`
  if (diffHours < 24) return `${diffHours} ч. назад`
  if (diffDays < 7) return `${diffDays} дн. назад`
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

watch(() => props.orgId, () => {
  reset()
  load()
})
watch(() => props.refreshTick, load)

load()
</script>
