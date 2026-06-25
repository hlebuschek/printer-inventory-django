<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-volume-mute text-warning"></i>
      <span class="fw-semibold">Молчащие принтеры</span>
      <select v-model.number="days" class="form-select form-select-sm ms-auto" style="width:auto;">
        <option :value="7">7 дней</option>
        <option :value="14">14 дней</option>
        <option :value="30">30 дней</option>
      </select>
    </div>
    <div class="card-body">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small">{{ error }}</div>
      <div v-else class="row g-3 text-center">
        <div class="col-4">
          <div class="display-6 fw-bold text-body">{{ data.total }}</div>
          <div class="small text-muted">Всего</div>
        </div>
        <div class="col-4">
          <div class="display-6 fw-bold text-warning">{{ data.silent }}</div>
          <div class="small text-muted">Молчат</div>
        </div>
        <div class="col-4">
          <div class="display-6 fw-bold text-success">{{ data.active_ok }}</div>
          <div class="small text-muted">Опрошены</div>
        </div>
        <div class="col-12 mt-2">
          <div class="progress" style="height: 8px;" :title="`${data.percentage}% молчат`">
            <div
              class="progress-bar bg-warning"
              role="progressbar"
              :style="`width: ${data.percentage}%`"
              :aria-valuenow="data.percentage"
              aria-valuemin="0"
              aria-valuemax="100"
            ></div>
          </div>
          <div class="small text-muted mt-1">
            {{ data.percentage }}% без успешного опроса за {{ days }} дн.
          </div>
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

const { loading, error, execute, reset } = useWidgetLoader()
const days = ref(7)
const data = ref({ total: 0, silent: 0, active_ok: 0, percentage: 0 })

async function load() {
  await execute(async () => {
    const params = new URLSearchParams({ days: days.value })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/silent-printers/?${params}`)
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data
  })
}

watch([() => props.orgId, days], () => {
  reset()
  load()
})
watch(() => props.refreshTick, load)

load()

defineExpose({ load })
</script>
