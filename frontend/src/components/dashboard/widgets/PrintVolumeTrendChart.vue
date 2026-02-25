<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2 flex-wrap">
      <i class="bi bi-graph-up text-success"></i>
      <span class="fw-semibold">Тренд объёма печати</span>
      <div class="btn-group btn-group-sm ms-auto" role="group">
        <button
          v-for="p in periods"
          :key="p.value"
          type="button"
          class="btn"
          :class="selectedMonths === p.value ? 'btn-success' : 'btn-outline-secondary'"
          @click="selectedMonths = p.value"
        >{{ p.label }}</button>
      </div>
      <button
        v-if="rows.length"
        type="button"
        class="btn btn-sm btn-outline-success"
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
      <div v-else-if="!hasData" class="text-muted small text-center my-auto">Нет данных monthly report</div>
      <canvas v-else ref="chartEl" style="max-height:220px;"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Filler,
} from 'chart.js'
import { fetchApi } from '../../../utils/api.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler)

const props = defineProps({
  orgId: { type: Number, default: null },
  refreshTick: { type: Number, default: 0 },
})

const periods = [
  { value: 0,  label: 'Все' },
  { value: 12, label: '12 мес' },
  { value: 6,  label: '6 мес' },
]
const selectedMonths = ref(0)

const loading = ref(true)
const error = ref(null)
const hasData = ref(false)
const chartEl = ref(null)
const rows = ref([])
let chartInstance = null

async function load() {
  loading.value = true
  error.value = null
  let data = null
  try {
    const params = new URLSearchParams({ months: selectedMonths.value })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/print-trend/?${params}`)
    if (!res.ok) { error.value = res.error || 'Ошибка'; return }
    data = res.data
    rows.value = data
    hasData.value = data.length > 0
  } catch (e) {
    error.value = 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
  if (hasData.value && data?.length) {
    await nextTick()
    renderChart(data)
  }
}

function renderChart(data) {
  if (!chartEl.value) return
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }

  const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark'
  const gridColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.18)'
  const textColor = isDark ? '#adb5bd' : '#6c757d'
  const pointRadius = data.length > 12 ? 3 : 5

  chartInstance = new Chart(chartEl.value, {
    type: 'line',
    data: {
      labels: data.map(r => r.label),
      datasets: [{
        label: 'Отпечатков',
        data: data.map(r => r.total),
        borderColor: '#198754',
        backgroundColor: 'rgba(25,135,84,0.15)',
        fill: true,
        tension: 0.3,
        pointRadius,
        pointHoverRadius: pointRadius + 3,
        pointHitRadius: 20,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          callbacks: {
            label: ctx => ` ${ctx.parsed.y.toLocaleString('ru-RU')} стр.`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxRotation: data.length > 12 ? 45 : 0,
          },
          grid: { color: gridColor, display: true },
        },
        y: {
          ticks: { color: textColor, callback: v => v.toLocaleString('ru-RU') },
          grid: { color: gridColor, display: true },
          beginAtZero: false,
        },
      },
    },
  })
}

function exportExcel() {
  const params = new URLSearchParams({ months: selectedMonths.value, format: 'xlsx' })
  if (props.orgId) params.set('org', props.orgId)
  window.location.href = `/dashboard/api/print-trend/export/?${params}`
}

watch([() => props.orgId, () => props.refreshTick, selectedMonths], load, { immediate: true })
onBeforeUnmount(() => { if (chartInstance) chartInstance.destroy() })
</script>
