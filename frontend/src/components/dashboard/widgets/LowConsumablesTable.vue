<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-exclamation-triangle text-warning"></i>
      <span class="fw-semibold">Расходники — критический уровень</span>
      <span v-if="!loading && data.length" class="badge bg-warning-subtle text-warning-emphasis ms-auto">
        {{ data.length }}
      </span>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:280px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-success small p-3 text-center">
        <i class="bi bi-check-circle"></i> Все расходники в норме
      </div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>IP</th>
            <th>Модель</th>
            <th>Организация</th>
            <th>Расходники</th>
            <th class="text-end">Мин%</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in data" :key="item.printer_id">
            <td class="font-monospace small">{{ item.ip_address }}</td>
            <td class="text-truncate" style="max-width:120px;" :title="item.model">{{ item.model }}</td>
            <td class="text-truncate" style="max-width:100px;" :title="item.organization">{{ item.organization }}</td>
            <td>
              <div class="d-flex flex-wrap gap-1">
                <span
                  v-for="(pct, name) in item.low_consumables"
                  :key="name"
                  class="badge"
                  :class="pct < 10 ? 'bg-danger' : 'bg-warning text-dark'"
                  :title="LABELS[name] || name"
                >
                  {{ SHORT_LABELS[name] || name }}: {{ pct }}%
                </span>
              </div>
            </td>
            <td class="text-end fw-semibold" :class="item.min_level < 10 ? 'text-danger' : 'text-warning'">
              {{ item.min_level }}%
            </td>
          </tr>
        </tbody>
      </table>
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

const LABELS = {
  toner_black: 'Тонер чёрный', toner_cyan: 'Тонер голубой',
  toner_magenta: 'Тонер пурпурный', toner_yellow: 'Тонер жёлтый',
  drum_black: 'Барабан чёрный', drum_cyan: 'Барабан голубой',
  drum_magenta: 'Барабан пурпурный', drum_yellow: 'Барабан жёлтый',
}
const SHORT_LABELS = {
  toner_black: 'TK', toner_cyan: 'TC', toner_magenta: 'TM', toner_yellow: 'TY',
  drum_black: 'DK', drum_cyan: 'DC', drum_magenta: 'DM', drum_yellow: 'DY',
}

async function load() {
  await execute(async () => {
    const params = new URLSearchParams()
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/low-consumables/?${params}`)
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
</script>
