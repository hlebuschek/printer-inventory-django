<template>
  <div class="card mb-3">
    <div class="card-body">
      <div v-if="loading" class="text-center py-4">
        <div class="spinner-border spinner-border-sm text-primary" role="status">
          <span class="visually-hidden">Загрузка...</span>
        </div>
      </div>

      <div v-else-if="error" class="alert alert-danger mb-0">{{ error }}</div>

      <template v-else>
        <div class="row g-3 mb-3">
          <div class="col-6 col-md-3">
            <div class="text-muted small text-uppercase">Заявок</div>
            <div class="h3 fw-semibold mb-0">{{ summary.total }}</div>
          </div>
          <div class="col-6 col-md-3">
            <div class="text-muted small text-uppercase">Незакрытых</div>
            <div class="h3 fw-semibold text-warning mb-0">{{ summary.active }}</div>
          </div>
          <div class="col-6 col-md-3">
            <div class="text-muted small text-uppercase">Просрочено</div>
            <div class="h3 fw-semibold text-danger mb-0">
              {{ summary.overdue }}<span class="fs-6 text-muted ms-2">{{ summary.overdue_share }}%</span>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="text-muted small text-uppercase" title="Рабочие часы по графику объекта">Простой, раб. ч</div>
            <div class="h3 fw-semibold mb-0">
              {{ summary.downtime_hours }}<span class="fs-6 text-muted ms-2">{{ summary.avg_downtime_hours }} на заявку</span>
            </div>
          </div>
        </div>

        <div v-if="hasDaily" class="mb-3">
          <canvas ref="dailyEl" style="max-height: 260px;"></canvas>
        </div>

        <div class="row g-3">
          <div class="col-12 col-lg-6">
            <BreakdownTable title="По подрядчикам" first-column="Подрядчик" :rows="analytics.by_provider" />
          </div>
          <div class="col-12 col-lg-6">
            <BreakdownTable title="По городам" first-column="Город" :rows="analytics.by_city" />
          </div>
          <div class="col-12">
            <BreakdownTable title="По организациям" first-column="Организация" :rows="analytics.by_organization" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js'
import BreakdownTable from './RequestAnalyticsBreakdown.vue'
import { fetchApi } from '../../utils/api'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const props = defineProps({
  query: { type: String, default: '' }
})

const loading = ref(true)
const error = ref('')
const analytics = reactive({ by_provider: [], by_city: [], by_organization: [], daily: [] })
const summary = reactive({ total: 0, active: 0, overdue: 0, overdue_share: 0, downtime_hours: 0, avg_downtime_hours: 0 })

const dailyEl = ref(null)
let dailyChart = null

const hasDaily = computed(() => analytics.daily.length > 0)

// Счёт запросов: пересчёт идёт по всей выборке и на широких фильтрах занимает
// секунды, поэтому ответ на отменённые фильтры не должен перетереть свежий
let requestId = 0

async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await fetchApi(`/contracts/api/requests/analytics/?${props.query}`)
    if (current !== requestId) return
    Object.assign(summary, data.summary)
    Object.assign(analytics, data)
  } catch (e) {
    if (current !== requestId) return
    error.value = 'Не удалось загрузить аналитику'
  } finally {
    if (current === requestId) loading.value = false
  }
  if (current !== requestId) return
  await nextTick()
  renderDaily()
}

function renderDaily() {
  // Канвас исчезает из DOM на время загрузки, поэтому график пересоздаём,
  // а не обновляем: у старого инстанса canvas уже удалён.
  if (dailyChart) {
    dailyChart.destroy()
    dailyChart = null
  }
  if (!hasDaily.value || !dailyEl.value) return

  const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark'
  const grid = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.18)'
  const text = isDark ? '#adb5bd' : '#6c757d'

  dailyChart = new Chart(dailyEl.value, {
    type: 'bar',
    data: {
      labels: analytics.daily.map((point) => `${point.date.slice(8, 10)}.${point.date.slice(5, 7)}`),
      datasets: [
        { label: 'Заведено', data: analytics.daily.map((p) => p.created), backgroundColor: 'rgba(13,110,253,0.7)' },
        { label: 'Восстановлено', data: analytics.daily.map((p) => p.restored), backgroundColor: 'rgba(25,135,84,0.7)' }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: text } } },
      scales: {
        x: { ticks: { color: text }, grid: { color: grid } },
        y: { ticks: { color: text, precision: 0 }, grid: { color: grid }, beginAtZero: true }
      }
    }
  })
}

watch(() => props.query, load, { immediate: true })

onBeforeUnmount(() => {
  if (dailyChart) dailyChart.destroy()
})
</script>
