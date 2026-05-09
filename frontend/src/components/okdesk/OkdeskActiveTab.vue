<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <span class="small text-muted">Создано:</span>
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
      <div class="btn-group btn-group-sm" role="group" aria-label="Быстрые периоды">
        <button class="btn btn-outline-secondary" @click="setRangeDays(7)">7д</button>
        <button class="btn btn-outline-secondary" @click="setRangeDays(30)">30д</button>
        <button class="btn btn-outline-secondary" @click="setRangeDays(90)">Квартал</button>
        <button
          class="btn btn-outline-secondary"
          :disabled="!dateFrom && !dateTo"
          @click="resetRange"
        >
          Сбросить
        </button>
      </div>
    </div>

    <div class="d-flex justify-content-between align-items-center mb-3">
      <div class="text-muted small">
        Всего активных заявок: <span class="fw-semibold">{{ totalActive }}</span>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-success btn-sm" @click="exportOpen = true">
          <i class="bi bi-file-earmark-excel"></i> Скачать XLSX
        </button>
        <a
          class="btn btn-outline-success btn-sm"
          href="/integrations/okdesk/export/active-all/"
          title="Excel со всеми активными, по листам на каждый статус"
        >
          <i class="bi bi-files"></i> По статусам
        </a>
      </div>
    </div>

    <OkdeskExportModal
      :open="exportOpen"
      scope="active"
      :filters="exportFilters"
      :filtered-count="totalActive"
      @close="exportOpen = false"
    />

    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else-if="!groups.length" class="text-center text-muted py-5">
      Нет активных заявок.
    </div>

    <div v-else class="row row-cols-1 row-cols-md-2 g-3">
      <div v-for="g in groups" :key="g.status" class="col">
        <div class="card shadow-sm h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span class="fw-semibold">{{ g.status }}</span>
            <span class="badge text-bg-primary">{{ g.count }}</span>
          </div>

          <ul v-if="g.samples?.length" class="list-group list-group-flush">
            <button
              v-for="issue in (expanded[g.status] ? fullList[g.status] || g.samples : g.samples)"
              :key="issue.issue_id"
              class="list-group-item list-group-item-action text-start"
              type="button"
              @click="$emit('open-issue', issue.issue_id)"
            >
              <div class="d-flex justify-content-between gap-2">
                <div class="flex-grow-1 min-w-0">
                  <div class="fw-semibold text-truncate">
                    <span class="text-muted me-1">#{{ issue.issue_id }}</span>
                    {{ issue.title || 'Без темы' }}
                  </div>
                  <div class="small text-muted text-truncate">
                    {{ issue.organization || issue.company_name || '—' }}
                    <span v-if="issue.serial_number" class="ms-2">
                      <i class="bi bi-upc-scan"></i> {{ issue.serial_number }}
                    </span>
                  </div>
                </div>
                <div class="text-end small text-nowrap">
                  <span v-if="issue.is_overdue" class="badge text-bg-danger d-block mb-1">
                    Просрочена
                  </span>
                  <span class="text-muted">{{ formatDate(issue.created_at) }}</span>
                </div>
              </div>
            </button>
          </ul>

          <div v-if="g.count > g.samples.length" class="card-footer d-flex justify-content-between gap-2">
            <button
              class="btn btn-link btn-sm p-0"
              @click="loadFull(g.status)"
              :disabled="loadingStatus === g.status"
            >
              <span v-if="!expanded[g.status]">
                Показать все {{ g.count }}
                <i class="bi bi-chevron-down"></i>
              </span>
              <span v-else>
                Скрыть
                <i class="bi bi-chevron-up"></i>
              </span>
            </button>
            <a
              class="btn btn-outline-success btn-sm"
              :href="`/integrations/okdesk/export/by-status/${encodeURIComponent(g.status)}/`"
              title="Экспорт этого статуса в Excel"
            >
              <i class="bi bi-file-earmark-excel"></i>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useToast } from '../../composables/useToast'
import OkdeskExportModal from './OkdeskExportModal.vue'

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  authorQuery: { type: Array, default: () => [] }
})
defineEmits(['open-issue'])

const groups = ref([])
const loading = ref(false)
const loadingStatus = ref(null)
const expanded = ref({})
const fullList = ref({})

const dateFrom = ref('')
const dateTo = ref('')

const exportOpen = ref(false)
const exportFilters = computed(() => ({
  q: props.searchQuery,
  authors: props.authorQuery,
  mine: props.onlyMine,
  date_from: dateFrom.value,
  date_to: dateTo.value
}))

const totalActive = computed(() => groups.value.reduce((acc, g) => acc + g.count, 0))

function buildParams(extra = {}) {
  const params = new URLSearchParams(extra)
  if (props.onlyMine) params.set('mine', 'true')
  if (props.searchQuery) params.set('q', props.searchQuery)
  for (const a of props.authorQuery || []) params.append('author', a)
  if (dateFrom.value) params.set('date_from', dateFrom.value)
  if (dateTo.value) params.set('date_to', dateTo.value)
  return params
}

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

function setRangeDays(days) {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - days + 1)
  dateFrom.value = isoDate(from)
  dateTo.value = isoDate(to)
}

function resetRange() {
  dateFrom.value = ''
  dateTo.value = ''
}

async function loadGroups() {
  loading.value = true
  try {
    const resp = await fetch(`/integrations/okdesk/api/active-grouped/?${buildParams()}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    groups.value = data.groups || []
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить активные: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function loadFull(status) {
  if (expanded.value[status]) {
    expanded.value[status] = false
    return
  }
  if (fullList.value[status]) {
    expanded.value[status] = true
    return
  }
  loadingStatus.value = status
  try {
    const resp = await fetch(
      `/integrations/okdesk/api/by-status/${encodeURIComponent(status)}/?${buildParams({ page: 1 })}`
    )
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    fullList.value[status] = data.issues || []
    expanded.value[status] = true
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить заявки: ${e.message}`, 'error')
  } finally {
    loadingStatus.value = null
  }
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch { return '' }
}

watch(
  () => [props.searchQuery, props.authorQuery, props.onlyMine, dateFrom.value, dateTo.value],
  () => {
    expanded.value = {}
    fullList.value = {}
    loadGroups()
  }
)

onMounted(loadGroups)
</script>

<style scoped>
.min-w-0 { min-width: 0; }
</style>
