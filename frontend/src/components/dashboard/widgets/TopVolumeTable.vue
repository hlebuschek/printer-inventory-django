<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-bar-chart-line text-primary"></i>
      <span class="fw-semibold">Топ по объёму печати</span>
      <select v-model.number="months" class="form-select form-select-sm ms-auto" style="width:auto;">
        <option :value="0">Всё время</option>
        <option :value="6">6 мес.</option>
        <option :value="12">12 мес.</option>
      </select>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:280px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-muted small p-3 text-center">
        Нет данных за период
      </div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>#</th>
            <th>Серийный №</th>
            <th>Модель</th>
            <th>Организация</th>
            <th class="text-end">Отпечатков</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in data" :key="item.serial_number + idx">
            <td class="text-muted">{{ idx + 1 }}</td>
            <td class="font-monospace small">{{ item.serial_number }}</td>
            <td class="text-truncate" style="max-width:120px;" :title="item.model">{{ item.model }}</td>
            <td class="text-truncate" style="max-width:100px;" :title="item.organization">{{ item.organization }}</td>
            <td class="text-end fw-semibold">{{ item.total.toLocaleString('ru-RU') }}</td>
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

const { loading, error, execute, reset } = useWidgetLoader()
const months = ref(0)
const data = ref([])

async function load() {
  await execute(async () => {
    const params = new URLSearchParams({ months: months.value, limit: 20 })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/top-by-volume/?${params}`)
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data
  })
}

watch([() => props.orgId, months], () => {
  reset()
  load()
})
watch(() => props.refreshTick, load)

load()

defineExpose({ load })
</script>
