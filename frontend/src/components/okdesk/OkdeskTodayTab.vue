<template>
  <div>
    <div class="d-flex flex-wrap align-items-center mb-3 gap-2">
      <div class="input-group input-group-sm" style="max-width: 240px;">
        <span class="input-group-text"><i class="bi bi-calendar3"></i></span>
        <input
          v-model="selectedDate"
          type="date"
          class="form-control"
          @change="reload"
        />
      </div>

      <button class="btn btn-outline-secondary btn-sm" @click="setRelativeDate(0)">
        Сегодня
      </button>
      <button class="btn btn-outline-secondary btn-sm" @click="setRelativeDate(-1)">
        Вчера
      </button>

      <div class="ms-auto d-flex gap-2">
        <a
          class="btn btn-success btn-sm"
          :href="`/integrations/okdesk/export/created/${selectedDate}/`"
        >
          <i class="bi bi-file-earmark-excel"></i> Создано · XLSX
        </a>
        <a
          class="btn btn-success btn-sm"
          :href="`/integrations/okdesk/export/closed/${selectedDate}/`"
        >
          <i class="bi bi-file-earmark-excel"></i> Закрыто · XLSX
        </a>
      </div>
    </div>

    <div v-if="loadingStats" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else>
      <div class="row g-3 mb-4">
        <div class="col-12 col-md-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Создано</div>
              <div class="display-6 fw-semibold text-primary">{{ stats.created_today }}</div>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Закрыто</div>
              <div class="display-6 fw-semibold text-success">{{ stats.closed_today }}</div>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <div class="text-muted small text-uppercase">Комментариев</div>
              <div class="display-6 fw-semibold text-info">{{ stats.comments_count }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card shadow-sm">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-chat-left-text"></i> Комментарии за день</span>
          <span class="text-muted small" v-if="commentsTotal > 0">
            {{ pageRangeFrom }}–{{ pageRangeTo }} из {{ commentsTotal }}
          </span>
        </div>

        <div v-if="loadingComments" class="card-body text-center py-4">
          <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
        </div>

        <div v-else-if="!comments.length" class="card-body text-center text-muted py-5">
          За эту дату комментариев нет.
        </div>

        <div v-else class="list-group list-group-flush">
          <button
            v-for="c in comments"
            :key="c.id"
            class="list-group-item list-group-item-action text-start"
            type="button"
            @click="$emit('open-issue', c.issue_id)"
          >
            <div class="d-flex justify-content-between gap-2">
              <div class="fw-semibold flex-grow-1 text-truncate">
                <span class="text-muted">#{{ c.issue_id }}</span>
                {{ c.issue_title }}
              </div>
              <small class="text-muted text-nowrap">{{ formatTime(c.created_at) }}</small>
            </div>
            <div class="small text-muted mt-1 comment-preview">
              <span class="fw-semibold">{{ c.author || 'Без автора' }}:</span>
              {{ c.content_preview }}
              <span
                v-if="!c.is_public"
                class="badge bg-secondary-subtle text-secondary-emphasis ms-1"
                title="Приватный комментарий"
              >приватный</span>
            </div>
          </button>
        </div>

        <div v-if="totalPages > 1" class="card-footer">
          <Pagination
            :current-page="page"
            :total-pages="totalPages"
            @page-change="onPageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useToast } from '../../composables/useToast'
import Pagination from '../common/Pagination.vue'

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false }
})
defineEmits(['open-issue'])

const todayIso = new Date().toISOString().slice(0, 10)
const selectedDate = ref(todayIso)
const stats = ref({ created_today: 0, closed_today: 0, comments_count: 0 })
const comments = ref([])
const commentsTotal = ref(0)
const totalPages = ref(0)
const page = ref(1)
const perPage = 50
const loadingStats = ref(false)
const loadingComments = ref(false)

const pageRangeFrom = computed(() => commentsTotal.value === 0 ? 0 : (page.value - 1) * perPage + 1)
const pageRangeTo = computed(() => Math.min(page.value * perPage, commentsTotal.value))

async function loadStats() {
  loadingStats.value = true
  try {
    const params = new URLSearchParams({ date: selectedDate.value })
    if (props.onlyMine) params.set('mine', 'true')
    const resp = await fetch(`/integrations/okdesk/api/daily-stats/?${params}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    stats.value = await resp.json()
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить статистику: ${e.message}`, 'error')
  } finally {
    loadingStats.value = false
  }
}

async function loadComments() {
  loadingComments.value = true
  try {
    const params = new URLSearchParams({ date: selectedDate.value, page: page.value, per_page: perPage })
    if (props.onlyMine) params.set('mine', 'true')
    const resp = await fetch(`/integrations/okdesk/api/daily-comments/?${params}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    comments.value = data.comments || []
    commentsTotal.value = data.total || 0
    totalPages.value = data.total_pages || 0
    page.value = data.page || 1
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить комментарии: ${e.message}`, 'error')
  } finally {
    loadingComments.value = false
  }
}

function reload() {
  page.value = 1
  loadStats()
  loadComments()
}

function onPageChange(p) {
  page.value = p
  loadComments()
}

function setRelativeDate(daysOffset) {
  const d = new Date()
  d.setDate(d.getDate() + daysOffset)
  selectedDate.value = d.toISOString().slice(0, 10)
  reload()
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

onMounted(() => {
  loadStats()
  loadComments()
})
</script>

<style scoped>
.comment-preview {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
