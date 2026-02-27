<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-broadcast text-primary"></i>
      <span class="fw-semibold">Статус принтеров</span>
      <span v-if="liveUpdated" class="badge bg-success-subtle text-success ms-auto small">
        <i class="bi bi-circle-fill" style="font-size:.5rem"></i> Live
      </span>
    </div>
    <div class="card-body">
      <!-- Спиннер только при первой загрузке -->
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small">{{ error }}</div>
      <div v-else class="row g-3 text-center">
        <div class="col-4">
          <div class="stat-value display-6 fw-bold text-body">{{ data.total }}</div>
          <div class="small text-muted">Всего</div>
        </div>
        <div class="col-4">
          <div class="stat-value display-6 fw-bold text-success">{{ data.online }}</div>
          <div class="small text-muted">Онлайн</div>
        </div>
        <div class="col-4">
          <div class="stat-value display-6 fw-bold text-danger">{{ data.offline }}</div>
          <div class="small text-muted">Офлайн</div>
        </div>
        <div class="col-12 mt-2">
          <div class="progress" style="height: 8px;" :title="`${data.percentage}% онлайн`">
            <div
              class="progress-bar bg-success"
              role="progressbar"
              :style="`width: ${data.percentage}%`"
              :aria-valuenow="data.percentage"
              aria-valuemin="0"
              aria-valuemax="100"
            ></div>
          </div>
          <div class="small text-muted mt-1">{{ data.percentage }}% устройств онлайн за 24ч</div>
        </div>
      </div>
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
const liveUpdated = ref(false)
const data = ref({ total: 0, online: 0, offline: 0, percentage: 0 })

async function load() {
  await execute(async () => {
    const params = new URLSearchParams()
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/printer-status/?${params}`)
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data
  })
}

watch(() => props.orgId, () => {
  reset()
  load()
})
watch(() => props.refreshTick, load)

load()

defineExpose({ load, markLive() { liveUpdated.value = true; setTimeout(() => { liveUpdated.value = false }, 5000) } })
</script>

<style scoped>
/* Плавное изменение цифр при фоновом обновлении */
.stat-value {
  transition: opacity 0.25s ease;
}
/* Прогресс-бар Bootstrap уже имеет transition на width */
</style>
