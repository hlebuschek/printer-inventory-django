<template>
  <div class="dashboard-page">
    <h1 class="h4 mb-3 d-flex align-items-center gap-2">
      <i class="bi bi-speedometer2"></i> Дашборд
    </h1>

    <DashboardFilters
      :organizations="organizations"
      v-model:modelOrgId="selectedOrgId"
      v-model:modelPeriod="selectedPeriod"
      :loading="anyLoading"
      @refresh="onRefresh"
    />

    <!-- Row 1: Статус принтеров + Статистика опросов + Тренд -->
    <div class="row g-3 mb-3">
      <div class="col-md-4 col-lg-3">
        <PrinterStatusCards
          ref="statusCardsRef"
          :org-id="selectedOrgId"
          :refresh-tick="refreshTick"
        />
      </div>
      <div class="col-md-4 col-lg-3">
        <PollStatsChart
          :org-id="selectedOrgId"
          :period="selectedPeriod"
          :refresh-tick="refreshTick"
        />
      </div>
      <div class="col-md-4 col-lg-6">
        <PrintVolumeTrendChart
          :org-id="selectedOrgId"
          :refresh-tick="refreshTick"
        />
      </div>
    </div>

    <!-- Row 2: Расходники + Топ проблемных -->
    <div class="row g-3 mb-3">
      <div class="col-lg-6">
        <LowConsumablesTable
          :org-id="selectedOrgId"
          :refresh-tick="refreshTick"
        />
      </div>
      <div class="col-lg-6">
        <ProblemPrintersTable
          :org-id="selectedOrgId"
          :period="selectedPeriod"
          :refresh-tick="refreshTick"
        />
      </div>
    </div>

    <!-- Row 3: Сводка по организациям + Последние опросы -->
    <div class="row g-3">
      <div class="col-lg-5">
        <OrgSummaryTable :refresh-tick="refreshTick" />
      </div>
      <div class="col-lg-7">
        <RecentActivityTable
          ref="recentActivityRef"
          :org-id="selectedOrgId"
          :refresh-tick="refreshTick"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted, onBeforeUnmount } from 'vue'
import DashboardFilters from './DashboardFilters.vue'
import PrinterStatusCards from './widgets/PrinterStatusCards.vue'
import PollStatsChart from './widgets/PollStatsChart.vue'
import LowConsumablesTable from './widgets/LowConsumablesTable.vue'
import ProblemPrintersTable from './widgets/ProblemPrintersTable.vue'
import PrintVolumeTrendChart from './widgets/PrintVolumeTrendChart.vue'
import OrgSummaryTable from './widgets/OrgSummaryTable.vue'
import RecentActivityTable from './widgets/RecentActivityTable.vue'

const appConfig = inject('appConfig', {})

// Список организаций из Django (передан через data-organizations)
const rawOrgs = appConfig.initialData?.organizations
  || JSON.parse(document.getElementById('dashboard-page')?.dataset?.organizations || '[]')

const organizations = ref(rawOrgs)
const selectedOrgId = ref(null)
const selectedPeriod = ref(7)
const refreshTick = ref(0)
const anyLoading = ref(false)

const statusCardsRef = ref(null)
const recentActivityRef = ref(null)

function onRefresh() {
  refreshTick.value++
}

// ─── WebSocket (подписка на inventory_updates) ─────────────────────────────
let ws = null
let wsReconnectTimer = null
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/inventory/`

function connectWs() {
  try {
    ws = new WebSocket(WS_URL)

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        // Обновляем виджеты, чувствительные к живым данным
        if (msg.type === 'inventory_update' || msg.type === 'inventory.update') {
          statusCardsRef.value?.load()
          statusCardsRef.value?.markLive()
          recentActivityRef.value?.load()
          recentActivityRef.value?.markLive()
        }
      } catch (_) { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      // Переподключение через 10 сек
      wsReconnectTimer = setTimeout(connectWs, 10000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  } catch (_) {
    // WebSocket недоступен (WSGI-сервер без Daphne)
  }
}

onMounted(connectWs)
onBeforeUnmount(() => {
  clearTimeout(wsReconnectTimer)
  ws?.close()
})
</script>

<style>
.widget-card {
  border-radius: .5rem;
}
.widget-card .card-header {
  font-size: .9rem;
  padding: .5rem .75rem;
}
</style>
