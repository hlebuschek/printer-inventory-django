<template>
  <div>
    <div class="d-flex flex-wrap align-items-center mb-3 gap-2">
      <div class="input-group input-group-sm" style="max-width: 320px;">
        <span class="input-group-text"><i class="bi bi-search"></i></span>
        <input
          v-model="searchQuery"
          type="text"
          class="form-control"
          placeholder="Поиск по теме или компании"
          @keyup.enter="reload"
        />
      </div>
      <button class="btn btn-outline-primary btn-sm" @click="reload">
        Найти
      </button>

      <div class="ms-auto small text-muted">
        Всего: <span class="fw-semibold">{{ total }}</span>
      </div>
    </div>

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
import { onMounted, ref } from 'vue'
import { useToast } from '../../composables/useToast'
import Pagination from '../common/Pagination.vue'

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false }
})
defineEmits(['open-issue'])

const issues = ref([])
const total = ref(0)
const totalPages = ref(0)
const page = ref(1)
const loading = ref(false)
const searchQuery = ref('')

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: page.value })
    if (searchQuery.value) params.append('q', searchQuery.value)
    if (props.onlyMine) params.set('mine', 'true')
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

function reload() {
  page.value = 1
  load()
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

onMounted(load)
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
