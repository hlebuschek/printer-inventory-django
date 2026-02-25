<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-pie-chart text-info"></i>
      <span class="fw-semibold">Статистика опросов</span>
      <button
        v-if="hasData"
        type="button"
        class="btn btn-sm btn-outline-secondary ms-auto"
        title="Экспорт в Excel"
        @click="exportExcel"
      >
        <i class="bi bi-file-earmark-excel"></i>
      </button>
    </div>
    <div class="card-body d-flex flex-column">
      <div v-if="loading" class="text-center py-3 m-auto">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small">{{ error }}</div>
      <div v-else-if="!hasData" class="text-muted small text-center my-auto">Нет данных за период</div>
      <div v-else class="flex-grow-1 d-flex flex-column">
        <canvas ref="chartEl" style="max-height:220px;"></canvas>
        <div class="mt-2">
          <div v-for="item in chartRows" :key="item.status" class="d-flex justify-content-between small">
            <span class="d-flex align-items-center gap-1">
              <span class="rounded-circle d-inline-block" :style="`width:10px;height:10px;background:${item.color}`"></span>
              {{ item.label }}
            </span>
            <span class="fw-semibold">{{ item.count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import {
  Chart,
  DoughnutController,
  ArcElement,
  Tooltip,
} from 'chart.js'
import { fetchApi } from '../../../utils/api.js'

Chart.register(DoughnutController, ArcElement, Tooltip)

const props = defineProps({
  orgId: { type: Number, default: null },
  period: { type: Number, default: 7 },
  refreshTick: { type: Number, default: 0 },
})

const loading = ref(true)
const error = ref(null)
const chartEl = ref(null)
const chartRows = ref([])
const hasData = ref(false)

let chartInstance = null

const STATUS_CONFIG = {
  SUCCESS:                  { label: 'Успешно',          color: '#198754' },
  FAILED:                   { label: 'Ошибка',           color: '#dc3545' },
  VALIDATION_ERROR:         { label: 'Ошибка валидации', color: '#fd7e14' },
  HISTORICAL_INCONSISTENCY: { label: 'Расхождение',      color: '#6c757d' },
}

async function load() {
  loading.value = true
  error.value = null
  let rows = null
  try {
    const params = new URLSearchParams({ period: props.period })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/poll-stats/?${params}`)
    if (!res.ok) { error.value = res.error || 'Ошибка'; return }

    rows = res.data.map(r => ({
      status: r.status,
      label: STATUS_CONFIG[r.status]?.label || r.status,
      color: STATUS_CONFIG[r.status]?.color || '#adb5bd',
      count: r.count,
    }))
    chartRows.value = rows
    hasData.value = rows.length > 0 && rows.some(r => r.count > 0)
  } catch (e) {
    error.value = 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
  // finally выполнился → loading=false → canvas появился в DOM
  if (hasData.value && rows?.length) {
    await nextTick()
    renderChart(rows)
  }
}

function renderChart(rows) {
  if (!chartEl.value) return
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }

  chartInstance = new Chart(chartEl.value, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r.label),
      datasets: [{
        data: rows.map(r => r.count),
        backgroundColor: rows.map(r => r.color),
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed}`,
          },
        },
      },
    },
  })
}

function exportExcel() {
  const params = new URLSearchParams({ period: props.period })
  if (props.orgId) params.set('org', props.orgId)
  window.location.href = `/dashboard/api/poll-stats/export/?${params}`
}

watch([() => props.orgId, () => props.period, () => props.refreshTick], load, { immediate: true })
onBeforeUnmount(() => { if (chartInstance) chartInstance.destroy() })
</script>
