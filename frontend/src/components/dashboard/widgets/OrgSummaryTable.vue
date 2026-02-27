<template>
  <div class="card h-100 widget-card">
    <div class="card-header d-flex align-items-center gap-2">
      <i class="bi bi-building text-secondary"></i>
      <span class="fw-semibold">Сводка по организациям</span>
      <span class="text-muted small ms-auto">нажмите на строку для деталей</span>
    </div>
    <div class="card-body p-0" style="overflow-y:auto; max-height:280px;">
      <div v-if="loading" class="text-center py-3">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="error" class="text-danger small p-3">{{ error }}</div>
      <div v-else-if="!data.length" class="text-muted small p-3 text-center">Нет данных</div>
      <table v-else class="table table-sm table-hover mb-0">
        <thead class="table-light sticky-top">
          <tr>
            <th>Организация</th>
            <th class="text-end">Всего</th>
            <th class="text-end">Онлайн</th>
            <th class="text-end text-danger">Офлайн</th>
            <th class="text-end">Online%</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in data"
            :key="row.org_id"
            class="cursor-pointer"
            @click="openDetail(row)"
            title="Нажмите для просмотра устройств"
          >
            <td class="text-truncate" style="max-width:180px;" :title="row.org_name">
              {{ row.org_name }}
            </td>
            <td class="text-end">{{ row.total_printers }}</td>
            <td class="text-end text-success fw-semibold">{{ row.online }}</td>
            <td class="text-end fw-semibold" :class="row.offline > 0 ? 'text-danger' : 'text-muted'">
              {{ row.offline }}
            </td>
            <td class="text-end">
              <div class="d-flex align-items-center justify-content-end gap-1">
                <div class="progress flex-grow-1" style="height:6px; max-width:60px;">
                  <div
                    class="progress-bar"
                    :class="row.online_pct >= 80 ? 'bg-success' : row.online_pct >= 50 ? 'bg-warning' : 'bg-danger'"
                    :style="`width:${row.online_pct}%`"
                  ></div>
                </div>
                <span class="small fw-semibold" style="min-width:32px; text-align:right;">{{ row.online_pct }}%</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Модал с деталями -->
  <OrgDetailModal
    :show="modal.show"
    :org-id="modal.orgId"
    :org-name="modal.orgName"
    @close="modal.show = false"
  />
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { fetchApi } from '../../../utils/api.js'
import { useWidgetLoader } from '../../../composables/useWidgetLoader.js'
import OrgDetailModal from './OrgDetailModal.vue'

const props = defineProps({
  refreshTick: { type: Number, default: 0 },
})

const { loading, error, initialized, execute } = useWidgetLoader()
const data = ref([])

const modal = reactive({ show: false, orgId: null, orgName: '' })

function openDetail(row) {
  modal.orgId = row.org_id
  modal.orgName = row.org_name
  modal.show = true
}

async function load() {
  await execute(async () => {
    const res = await fetchApi('/dashboard/api/org-summary/')
    if (!res.ok) throw new Error(res.error || 'Ошибка загрузки')
    data.value = res.data
  })
}

watch(() => props.refreshTick, load)

load()
</script>

<style scoped>
.cursor-pointer { cursor: pointer; }
</style>
