<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-pie-chart text-info"></i>
      <span class="fw-semibold">Принтеры по производителям</span>
    </div>
    <div class="card-body" style="overflow-y:auto; max-height:280px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small">{{ error }}</div>
      <div v-else-if="!data.length" class="text-muted small text-center">
        Нет данных
      </div>
      <div v-else>
        <div v-for="item in data" :key="item.manufacturer" class="mb-2">
          <div class="d-flex justify-content-between small mb-1">
            <span class="text-truncate" :title="item.manufacturer">{{ item.manufacturer }}</span>
            <span class="fw-semibold ms-2">{{ item.count }}</span>
          </div>
          <div class="progress" style="height: 6px;">
            <div
              class="progress-bar bg-info"
              role="progressbar"
              :style="`width: ${pct(item.count)}%`"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { fetchApi } from '../../../utils/api.js'
import { useWidgetLoader } from '../../../composables/useWidgetLoader.js'

const props = defineProps({
  orgId: { type: Number, default: null },
  refreshTick: { type: Number, default: 0 },
})

const { loading, error, execute, reset } = useWidgetLoader()
const data = ref([])

const maxCount = computed(() => data.value.reduce((m, x) => Math.max(m, x.count), 0) || 1)
function pct(count) {
  return Math.round((count / maxCount.value) * 100)
}

async function load() {
  await execute(async () => {
    const params = new URLSearchParams()
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/manufacturer-distribution/?${params}`)
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

defineExpose({ load })
</script>
