<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <span class="small text-muted">Период:</span>
      <input
        v-model="dateFrom"
        type="date"
        class="form-control form-control-sm"
        style="max-width: 160px;"
      />
      <span class="text-muted">—</span>
      <input
        v-model="dateTo"
        type="date"
        class="form-control form-control-sm"
        style="max-width: 160px;"
      />
      <div class="btn-group btn-group-sm" role="group">
        <button class="btn btn-outline-secondary" @click="setRangeDays(7)">7д</button>
        <button class="btn btn-outline-secondary" @click="setRangeDays(30)">30д</button>
        <button class="btn btn-outline-secondary" @click="setRangeDays(90)">Квартал</button>
      </div>

      <div class="form-check form-switch ms-2" title="При включении среднее/медиана считаются только по заявкам, СОЗДАННЫМ в выбранном периоде">
        <input
          id="only-period-created"
          v-model="onlyPeriodCreated"
          class="form-check-input"
          type="checkbox"
          role="switch"
        />
        <label class="form-check-label small" for="only-period-created">
          Только созданные в периоде
        </label>
      </div>
    </div>

    <div v-if="loading && !initialized" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else class="position-relative">
      <div v-if="loading" class="analytics-overlay">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Загрузка...</span>
        </div>
      </div>

      <div class="row g-3 mb-4">
        <div class="col-6 col-md-3">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Создано</div>
              <div class="display-6 fw-semibold text-primary">{{ totals.created }}</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Закрыто</div>
              <div class="display-6 fw-semibold text-success">{{ totals.closed }}</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Активны сейчас</div>
              <div class="display-6 fw-semibold text-warning">{{ totals.active_now }}</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Время решения</div>
              <div class="d-flex align-items-baseline gap-3 mt-1">
                <div>
                  <div class="h4 fw-semibold text-info mb-0">
                    {{ formatHours(resolution.median_hours) }}
                  </div>
                  <div class="small text-muted">медиана</div>
                </div>
                <div>
                  <div class="h6 fw-semibold text-secondary mb-0">
                    {{ formatHours(resolution.avg_hours) }}
                  </div>
                  <div class="small text-muted">среднее</div>
                </div>
              </div>
              <div class="small text-muted mt-1">
                выборка: {{ resolution.sample_size || 0 }} заявок
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="row g-3">
        <div class="col-12 col-lg-7">
          <div class="card shadow-sm h-100">
            <div class="card-header">
              <i class="bi bi-graph-up"></i> Создано / Закрыто по дням
            </div>
            <div class="card-body">
              <canvas v-if="hasTimeseries" ref="timeseriesEl" style="max-height: 320px;"></canvas>
              <div v-else class="text-center text-muted py-5">
                Нет данных за выбранный период
              </div>
            </div>
          </div>
        </div>

        <div class="col-12 col-lg-5">
          <div class="card shadow-sm h-100">
            <div class="card-header">
              <i class="bi bi-trophy"></i> Топ исполнителей · закрыто
            </div>
            <div class="card-body">
              <canvas v-if="topAssignees.length" ref="assigneesEl" style="max-height: 320px;"></canvas>
              <div v-else class="text-center text-muted py-5">
                В периоде нет закрытых заявок с указанным исполнителем
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Filler,
  Legend,
  BarController,
  BarElement,
} from 'chart.js'
import { useToast } from '../../composables/useToast'

Chart.register(
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Filler,
  Legend,
  BarController,
  BarElement,
)

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  authorQuery: { type: Array, default: () => [] }
})

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

function defaultRange(days) {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - days + 1)
  return { from: isoDate(from), to: isoDate(to) }
}

const initial = defaultRange(30)
const dateFrom = ref(initial.from)
const dateTo = ref(initial.to)

function setRangeDays(days) {
  const r = defaultRange(days)
  dateFrom.value = r.from
  dateTo.value = r.to
}

const loading = ref(false)
const initialized = ref(false)
const onlyPeriodCreated = ref(false)
const totals = ref({ created: 0, closed: 0, active_now: 0 })
const resolution = ref({ avg_hours: null, median_hours: null, sample_size: 0 })
const timeseries = ref([])
const topAssignees = ref([])

const hasTimeseries = computed(
  () => timeseries.value.length > 0 && timeseries.value.some((p) => p.created || p.closed)
)

const timeseriesEl = ref(null)
const assigneesEl = ref(null)
let timeseriesChart = null
let assigneesChart = null

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      date_from: dateFrom.value,
      date_to: dateTo.value,
    })
    if (props.onlyMine) params.set('mine', 'true')
    if (props.searchQuery) params.set('q', props.searchQuery)
    for (const a of props.authorQuery || []) params.append('author', a)
    if (onlyPeriodCreated.value) params.set('only_period_created', 'true')
    const resp = await fetch(`/integrations/okdesk/api/analytics/?${params}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    totals.value = data.totals || {}
    resolution.value = data.totals?.resolution || { avg_hours: null, median_hours: null, sample_size: 0 }
    timeseries.value = data.timeseries || []
    topAssignees.value = data.top_assignees || []
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить аналитику: ${e.message}`, 'error')
  } finally {
    loading.value = false
    initialized.value = true
  }
  await nextTick()
  renderTimeseries()
  renderAssignees()
}

function themeColors() {
  const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark'
  return {
    grid: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.18)',
    text: isDark ? '#adb5bd' : '#6c757d',
  }
}

function formatLabel(iso) {
  // YYYY-MM-DD → DD.MM
  if (!iso || iso.length < 10) return iso || ''
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}`
}

function formatHours(h) {
  if (h === null || h === undefined) return '—'
  if (h < 24) return `${h.toFixed(1)} ч`
  const days = Math.floor(h / 24)
  const rest = Math.round(h - days * 24)
  return rest ? `${days} дн ${rest} ч` : `${days} дн`
}

function renderTimeseries() {
  // Канвас перевешивается из DOM при каждом loading-цикле, поэтому всегда
  // пересоздаём график — попытка update() на старом инстансе ломается, т.к.
  // его canvas уже удалён.
  if (timeseriesChart) {
    timeseriesChart.destroy()
    timeseriesChart = null
  }
  if (!hasTimeseries.value || !timeseriesEl.value) return
  const labels = timeseries.value.map((p) => formatLabel(p.date))
  const created = timeseries.value.map((p) => p.created)
  const closed = timeseries.value.map((p) => p.closed)
  const { grid, text } = themeColors()

  timeseriesChart = new Chart(timeseriesEl.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Создано',
          data: created,
          borderColor: '#0d6efd',
          backgroundColor: 'rgba(13,110,253,0.12)',
          tension: 0.3,
          fill: true,
        },
        {
          label: 'Закрыто',
          data: closed,
          borderColor: '#198754',
          backgroundColor: 'rgba(25,135,84,0.12)',
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, labels: { color: text } },
        tooltip: { enabled: true },
      },
      scales: {
        x: { ticks: { color: text }, grid: { color: grid } },
        y: { ticks: { color: text, precision: 0 }, grid: { color: grid }, beginAtZero: true },
      },
    },
  })
}

function renderAssignees() {
  if (assigneesChart) {
    assigneesChart.destroy()
    assigneesChart = null
  }
  if (!topAssignees.value.length || !assigneesEl.value) return
  const labels = topAssignees.value.map((r) => r.assignee)
  const data = topAssignees.value.map((r) => r.closed)
  const { grid, text } = themeColors()

  assigneesChart = new Chart(assigneesEl.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Закрыто',
          data,
          backgroundColor: 'rgba(25,135,84,0.7)',
          borderColor: '#198754',
          borderWidth: 1,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true },
      },
      scales: {
        x: { ticks: { color: text, precision: 0 }, grid: { color: grid }, beginAtZero: true },
        y: { ticks: { color: text }, grid: { color: grid } },
      },
    },
  })
}

watch(
  () => [
    dateFrom.value,
    dateTo.value,
    onlyPeriodCreated.value,
    props.onlyMine,
    props.searchQuery,
    props.authorQuery,
  ],
  load
)

onMounted(load)

onBeforeUnmount(() => {
  if (timeseriesChart) timeseriesChart.destroy()
  if (assigneesChart) assigneesChart.destroy()
})
</script>

<style scoped>
.analytics-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bs-body-bg);
  opacity: 0.6;
  z-index: 5;
  border-radius: 0.375rem;
  pointer-events: none;
}
</style>
