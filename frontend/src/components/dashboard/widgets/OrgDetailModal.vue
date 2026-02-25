<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="modal fade show d-block"
      tabindex="-1"
      style="background:rgba(0,0,0,.45);"
      @mousedown.self="close"
    >
      <div class="modal-dialog modal-xl modal-dialog-scrollable">
        <div class="modal-content">

          <!-- Header -->
          <div class="modal-header">
            <div>
              <h5 class="modal-title mb-0">
                <i class="bi bi-building me-2"></i>{{ orgName }}
              </h5>
              <div class="d-flex gap-3 mt-1 small">
                <span class="text-muted">Всего: <strong>{{ allDevices.length }}</strong></span>
                <span class="text-success">
                  <i class="bi bi-circle-fill" style="font-size:.5rem;"></i>
                  Онлайн: <strong>{{ onlineCount }}</strong>
                </span>
                <span class="text-danger">
                  <i class="bi bi-circle-fill" style="font-size:.5rem;"></i>
                  Офлайн: <strong>{{ offlineCount }}</strong>
                </span>
              </div>
            </div>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <!-- Filter bar -->
          <div class="modal-header py-2 border-bottom">
            <div class="d-flex align-items-center gap-2 flex-wrap w-100">
              <!-- Статус -->
              <div class="btn-group btn-group-sm">
                <button
                  v-for="f in statusFilters"
                  :key="f.value"
                  class="btn"
                  :class="statusFilter === f.value ? f.activeClass : 'btn-outline-secondary'"
                  @click="statusFilter = f.value"
                >
                  <i :class="f.icon"></i> {{ f.label }}
                  <span class="badge ms-1" :class="f.badgeClass">{{ f.count }}</span>
                </button>
              </div>

              <!-- Поиск -->
              <div class="input-group input-group-sm ms-auto" style="max-width:260px;">
                <span class="input-group-text"><i class="bi bi-search"></i></span>
                <input
                  v-model="search"
                  type="text"
                  class="form-control"
                  placeholder="IP, модель, серийник…"
                >
                <button v-if="search" class="btn btn-outline-secondary" @click="search=''">
                  <i class="bi bi-x"></i>
                </button>
              </div>

              <!-- Экспорт -->
              <button class="btn btn-sm btn-outline-success" @click="exportExcel" title="Экспорт в Excel">
                <i class="bi bi-file-earmark-excel"></i>
              </button>
            </div>
          </div>

          <!-- Body -->
          <div class="modal-body p-0">
            <div v-if="loading" class="text-center py-5">
              <div class="spinner-border text-primary"></div>
            </div>
            <div v-else-if="!filteredDevices.length" class="text-center text-muted py-5">
              <i class="bi bi-inbox fs-2 d-block mb-2"></i>
              Нет устройств по выбранному фильтру
            </div>
            <div v-else class="table-responsive">
              <table class="table table-sm table-hover mb-0 align-middle">
                <thead class="table-light sticky-top">
                  <tr>
                    <th style="width:36px;"></th>
                    <th @click="sortBy('ip_address')" class="sortable">
                      IP <i :class="sortIcon('ip_address')"></i>
                    </th>
                    <th @click="sortBy('model')" class="sortable">
                      Модель <i :class="sortIcon('model')"></i>
                    </th>
                    <th>Серийный номер</th>
                    <th @click="sortBy('last_poll')" class="sortable">
                      Последний опрос <i :class="sortIcon('last_poll')"></i>
                    </th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in sortedDevices" :key="d.printer_id">
                    <td class="text-center">
                      <span
                        class="rounded-circle d-inline-block"
                        :class="d.is_online ? 'bg-success' : 'bg-danger'"
                        style="width:10px;height:10px;"
                        :title="d.is_online ? 'Онлайн' : 'Офлайн'"
                      ></span>
                    </td>
                    <td class="font-monospace">{{ d.ip_address }}</td>
                    <td class="text-truncate" style="max-width:200px;" :title="d.model">{{ d.model || '—' }}</td>
                    <td class="font-monospace small text-muted">{{ d.serial_number || '—' }}</td>
                    <td class="small text-muted text-nowrap">{{ formatTime(d.last_poll) }}</td>
                    <td>
                      <span class="badge" :class="STATUS_BADGE[d.last_status] || 'bg-secondary'">
                        {{ STATUS_LABEL[d.last_status] || d.last_status }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-footer py-2">
            <span class="text-muted small me-auto">
              Показано {{ sortedDevices.length }} из {{ allDevices.length }} устройств
            </span>
            <button class="btn btn-sm btn-secondary" @click="close">Закрыть</button>
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { fetchApi } from '../../../utils/api.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  orgId: { type: Number, default: null },
  orgName: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const loading = ref(false)
const allDevices = ref([])
const statusFilter = ref('all')
const search = ref('')
const sortKey = ref('ip_address')
const sortDir = ref(1)  // 1=asc, -1=desc

const STATUS_BADGE = {
  SUCCESS: 'bg-success',
  FAILED: 'bg-danger',
  VALIDATION_ERROR: 'bg-warning text-dark',
  HISTORICAL_INCONSISTENCY: 'bg-secondary',
}
const STATUS_LABEL = {
  SUCCESS: 'OK',
  FAILED: 'Ошибка',
  VALIDATION_ERROR: 'Валидация',
  HISTORICAL_INCONSISTENCY: 'Расхожд.',
  '—': '—',
}

const onlineCount = computed(() => allDevices.value.filter(d => d.is_online).length)
const offlineCount = computed(() => allDevices.value.filter(d => !d.is_online).length)

const statusFilters = computed(() => [
  { value: 'all',    label: 'Все',     icon: 'bi bi-list',         activeClass: 'btn-secondary',  badgeClass: 'bg-secondary', count: allDevices.value.length },
  { value: 'online', label: 'Онлайн',  icon: 'bi bi-circle-fill',  activeClass: 'btn-success',    badgeClass: 'bg-success',   count: onlineCount.value },
  { value: 'offline',label: 'Офлайн',  icon: 'bi bi-circle',       activeClass: 'btn-danger',     badgeClass: 'bg-danger',    count: offlineCount.value },
])

const filteredDevices = computed(() => {
  let list = allDevices.value
  if (statusFilter.value === 'online')  list = list.filter(d => d.is_online)
  if (statusFilter.value === 'offline') list = list.filter(d => !d.is_online)
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    list = list.filter(d =>
      d.ip_address?.toLowerCase().includes(q) ||
      d.model?.toLowerCase().includes(q) ||
      d.serial_number?.toLowerCase().includes(q)
    )
  }
  return list
})

const sortedDevices = computed(() => {
  return [...filteredDevices.value].sort((a, b) => {
    const va = a[sortKey.value] ?? ''
    const vb = b[sortKey.value] ?? ''
    if (va < vb) return -sortDir.value
    if (va > vb) return sortDir.value
    return 0
  })
})

function sortBy(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else { sortKey.value = key; sortDir.value = 1 }
}

function sortIcon(key) {
  if (sortKey.value !== key) return 'bi bi-arrow-down-up text-muted opacity-50'
  return sortDir.value === 1 ? 'bi bi-arrow-up' : 'bi bi-arrow-down'
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadDevices() {
  if (!props.orgId) return
  loading.value = true
  allDevices.value = []
  try {
    const res = await fetchApi(`/dashboard/api/org-devices/?org=${props.orgId}`)
    if (res.ok) allDevices.value = res.data
  } catch (_) {}
  finally { loading.value = false }
}

function close() { emit('close') }

function exportExcel() {
  const params = new URLSearchParams({ org: props.orgId })
  if (statusFilter.value !== 'all') params.set('status', statusFilter.value)
  window.location.href = `/dashboard/api/org-devices/export/?${params}`
}

watch(() => props.show, (val) => {
  if (val) {
    statusFilter.value = 'offline'  // по умолчанию показываем офлайн
    search.value = ''
    sortKey.value = 'ip_address'
    sortDir.value = 1
    loadDevices()
  }
})
</script>

<style scoped>
.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
.sortable:hover { background: var(--bs-table-hover-bg); }
</style>
