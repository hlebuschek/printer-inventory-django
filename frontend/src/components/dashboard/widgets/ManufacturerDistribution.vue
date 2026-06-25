<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-pie-chart text-info"></i>
      <span class="fw-semibold">Принтеры по производителям</span>
      <span v-if="!loading && total" class="badge bg-secondary ms-auto">{{ total }}</span>
    </div>
    <div class="card-body d-flex flex-column" style="overflow:hidden; max-height:320px;">
      <div class="row g-2 mb-2">
        <div :class="source === 'monthly' ? 'col-12' : 'col-12'">
          <select v-model="source" class="form-select form-select-sm" @change="load">
            <option value="polling">По опросу</option>
            <option value="contracts">По договорам</option>
            <option value="monthly">По отчётам</option>
          </select>
        </div>
        <template v-if="source === 'monthly'">
          <div class="col-6">
            <select v-model="monthFrom" class="form-select form-select-sm" @change="load">
              <option v-for="m in months" :key="'f' + m" :value="m">с {{ m }}</option>
            </select>
          </div>
          <div class="col-6">
            <select v-model="monthTo" class="form-select form-select-sm" @change="load">
              <option v-for="m in months" :key="'t' + m" :value="m">по {{ m }}</option>
            </select>
          </div>
        </template>
      </div>

      <div class="flex-grow-1" style="overflow-y:auto;">
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
const source = ref('polling')
const months = ref([])
const monthFrom = ref('')
const monthTo = ref('')

const maxCount = computed(() => data.value.reduce((m, x) => Math.max(m, x.count), 0) || 1)
const total = computed(() => data.value.reduce((s, x) => s + x.count, 0))
function pct(count) {
  return Math.round((count / maxCount.value) * 100)
}

async function loadMonths() {
  if (months.value.length) return
  try {
    const res = await fetchApi('/dashboard/api/report-months/')
    if (res.ok && Array.isArray(res.data) && res.data.length) {
      months.value = res.data
      monthTo.value = res.data[0]
      monthFrom.value = res.data[res.data.length - 1]
    }
  } catch (e) {
    // отчётный список не критичен — без него monthly просто берёт весь период
  }
}

async function load() {
  if (source.value === 'monthly') await loadMonths()
  await execute(async () => {
    const params = new URLSearchParams({ source: source.value })
    if (props.orgId) params.set('org', props.orgId)
    if (source.value === 'monthly') {
      if (monthFrom.value) params.set('month_from', monthFrom.value)
      if (monthTo.value) params.set('month_to', monthTo.value)
    }
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
