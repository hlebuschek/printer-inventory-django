<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <span class="small text-muted">Закрыто:</span>
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

      <div class="ms-auto d-flex align-items-center gap-2">
        <div class="small text-muted">
          Всего: <span class="fw-semibold">{{ total }}</span>
        </div>
        <button class="btn btn-success btn-sm" @click="exportOpen = true">
          <i class="bi bi-file-earmark-excel"></i> Скачать XLSX
        </button>
      </div>
    </div>

    <OkdeskExportModal
      :open="exportOpen"
      scope="closed"
      :filters="exportFilters"
      :filtered-count="total"
      @close="exportOpen = false"
    />

    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else-if="!issues.length" class="text-center text-muted py-5">
      Закрытых заявок не найдено.
    </div>

    <div v-else class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th style="width: 80px;">#</th>
              <th>Заголовок</th>
              <th class="d-none d-md-table-cell">Компания</th>
              <th class="d-none d-md-table-cell">Серийник</th>
              <th class="d-none d-lg-table-cell">Исполнитель</th>
              <th style="width: 110px;">Создана</th>
              <th style="width: 110px;">Закрыта</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="issue in issues"
              :key="issue.issue_id"
              class="cursor-pointer"
              @click="$emit('open-issue', issue.issue_id)"
            >
              <td class="text-muted">{{ issue.issue_id }}</td>
              <td class="fw-semibold">{{ issue.title || 'Без темы' }}</td>
              <td class="d-none d-md-table-cell text-truncate" style="max-width: 220px;">
                {{ issue.organization || issue.company_name || '—' }}
              </td>
              <td class="d-none d-md-table-cell">{{ issue.serial_number || '—' }}</td>
              <td class="d-none d-lg-table-cell">{{ issue.assignee_name || '—' }}</td>
              <td class="text-nowrap">{{ formatDate(issue.created_at) }}</td>
              <td class="text-nowrap">{{ formatDate(issue.completed_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      class="mt-3"
      @page-change="onPageChange"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useToast } from '../../composables/useToast'
import Pagination from '../common/Pagination.vue'
import OkdeskExportModal from './OkdeskExportModal.vue'

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  authorQuery: { type: Array, default: () => [] }
})
defineEmits(['open-issue'])

const issues = ref([])
const total = ref(0)
const totalPages = ref(0)
const page = ref(1)
const loading = ref(false)

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

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: page.value })
    if (props.searchQuery) params.append('q', props.searchQuery)
    for (const a of props.authorQuery || []) params.append('author', a)
    if (props.onlyMine) params.set('mine', 'true')
    if (dateFrom.value) params.set('date_from', dateFrom.value)
    if (dateTo.value) params.set('date_to', dateTo.value)
    const resp = await fetch(`/integrations/okdesk/api/closed/?${params}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    issues.value = data.issues || []
    total.value = data.total || 0
    totalPages.value = data.total_pages || 0
    page.value = data.page || 1
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить закрытые заявки: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

function onPageChange(p) {
  page.value = p
  load()
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
    page.value = 1
    load()
  }
)

onMounted(load)
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
