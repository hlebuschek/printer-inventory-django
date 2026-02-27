<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-bug text-danger"></i>
      <span class="fw-semibold">Топ проблемных принтеров</span>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:280px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-success small p-3 text-center">
        <i class="bi bi-check-circle"></i> Нет ошибок за период
      </div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>#</th>
            <th>IP</th>
            <th>Модель</th>
            <th>Организация</th>
            <th class="text-end">Ошибки</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in data" :key="item.printer_id">
            <td class="text-muted">{{ idx + 1 }}</td>
            <td class="font-monospace small">{{ item.ip_address }}</td>
            <td class="text-truncate" style="max-width:120px;" :title="item.model">{{ item.model || '—' }}</td>
            <td class="text-truncate" style="max-width:100px;" :title="item.organization">{{ item.organization }}</td>
            <td class="text-end">
              <span class="badge bg-danger-subtle text-danger-emphasis fw-semibold">
                {{ item.failure_count }}
              </span>
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
  period: { type: Number, default: 7 },
  refreshTick: { type: Number, default: 0 },
})

const { loading, error, initialized, execute, reset } = useWidgetLoader()
const data = ref([])

async function load() {
  await execute(async () => {
    const params = new URLSearchParams({ period: props.period })
    if (props.orgId) params.set('org', props.orgId)
    const res = await fetchApi(`/dashboard/api/problem-printers/?${params}`)
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data
  })
}

watch([() => props.orgId, () => props.period], () => {
  reset()
  load()
})
watch(() => props.refreshTick, load)

load()
</script>
