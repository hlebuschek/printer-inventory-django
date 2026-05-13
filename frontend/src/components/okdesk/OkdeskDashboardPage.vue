<template>
  <div class="okdesk-dashboard-page">
    <ToastContainer />

    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
      <h1 class="h4 mb-0">Service Desk</h1>

      <div class="d-flex align-items-center gap-2">
        <div
          class="btn-group btn-group-sm"
          role="group"
          aria-label="Фильтр по автору"
          v-if="userContext?.okdesk_name"
        >
          <button
            type="button"
            class="btn"
            :class="onlyMine ? 'btn-outline-primary' : 'btn-primary'"
            :disabled="!onlyMine"
            @click="onlyMine = false"
          >
            Все
          </button>
          <button
            type="button"
            class="btn"
            :class="onlyMine ? 'btn-primary' : 'btn-outline-primary'"
            :disabled="onlyMine"
            @click="onlyMine = true"
            :title="`Показать только заявки от ${userContext.okdesk_name}`"
          >
            <i class="bi bi-person-check"></i> Только мои
          </button>
        </div>

        <button
          type="button"
          class="btn btn-outline-primary btn-sm"
          :disabled="syncing"
          @click="syncNow"
          title="Запустить синхронизацию заявок и комментариев из Okdesk сейчас"
        >
          <span
            v-if="syncing"
            class="spinner-border spinner-border-sm me-1"
            role="status"
            aria-hidden="true"
          ></span>
          <i v-else class="bi bi-arrow-clockwise"></i>
          {{ syncing ? 'Синхронизация...' : 'Обновить из Okdesk' }}
        </button>
      </div>
    </div>

    <div class="d-flex flex-wrap align-items-center mb-3 gap-2">
      <div class="input-group input-group-sm" style="max-width: 320px;">
        <span class="input-group-text"><i class="bi bi-search"></i></span>
        <input
          v-model="searchInput"
          type="text"
          class="form-control"
          placeholder="Серийник, организация, тема"
          @keyup.enter="applyFilters"
        />
      </div>
      <div style="min-width: 260px; max-width: 360px; flex: 1 1 260px;">
        <OkdeskAuthorMultiSelect
          v-model="authorQuery"
          :options="authorOptions"
        />
      </div>
      <button class="btn btn-outline-primary btn-sm" @click="applyFilters">
        Применить
      </button>
      <button
        class="btn btn-outline-secondary btn-sm"
        @click="resetFilters"
        :disabled="!hasActiveFilters && !searchInput"
      >
        Сбросить
      </button>

      <div v-if="hasActiveFilters" class="ms-auto small text-muted">
        Активные фильтры:
        <span v-if="searchQuery" class="badge text-bg-light border me-1">
          поиск: {{ searchQuery }}
        </span>
        <span v-if="authorQuery.length" class="badge text-bg-light border">
          инициаторов: {{ authorQuery.length }}
        </span>
      </div>
    </div>

    <ul class="nav nav-tabs mb-3" role="tablist">
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeTab === 'today' }"
          type="button"
          @click="activeTab = 'today'"
        >
          <i class="bi bi-calendar-day"></i> Сегодня
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeTab === 'active' }"
          type="button"
          @click="activeTab = 'active'"
        >
          <i class="bi bi-list-check"></i> Активные
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeTab === 'closed' }"
          type="button"
          @click="activeTab = 'closed'"
        >
          <i class="bi bi-archive"></i> Закрытые
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeTab === 'analytics' }"
          type="button"
          @click="activeTab = 'analytics'"
        >
          <i class="bi bi-bar-chart-line"></i> Аналитика
        </button>
      </li>
    </ul>

    <div v-if="activeTab === 'today'">
      <OkdeskTodayTab
        :key="`today-${refreshKey}`"
        :only-mine="onlyMine"
        :search-query="searchQuery"
        :author-query="authorQuery"
        @open-issue="openIssueDetail"
      />
    </div>

    <div v-else-if="activeTab === 'active'">
      <OkdeskActiveTab
        :key="`active-${refreshKey}`"
        :only-mine="onlyMine"
        :search-query="searchQuery"
        :author-query="authorQuery"
        @open-issue="openIssueDetail"
      />
    </div>

    <div v-else-if="activeTab === 'closed'">
      <OkdeskClosedTab
        :key="`closed-${refreshKey}`"
        :only-mine="onlyMine"
        :search-query="searchQuery"
        :author-query="authorQuery"
        @open-issue="openIssueDetail"
      />
    </div>

    <div v-else-if="activeTab === 'analytics'">
      <OkdeskAnalyticsTab
        :key="`analytics-${refreshKey}`"
        :only-mine="onlyMine"
        :search-query="searchQuery"
        :author-query="authorQuery"
      />
    </div>

    <OkdeskIssueDetailModal
      v-model:issue-id="detailIssueId"
      :permissions="permissions"
      :user-context="userContext"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import ToastContainer from '../common/ToastContainer.vue'
import OkdeskTodayTab from './OkdeskTodayTab.vue'
import OkdeskActiveTab from './OkdeskActiveTab.vue'
import OkdeskClosedTab from './OkdeskClosedTab.vue'
import OkdeskAnalyticsTab from './OkdeskAnalyticsTab.vue'
import OkdeskIssueDetailModal from './OkdeskIssueDetailModal.vue'
import OkdeskAuthorMultiSelect from './OkdeskAuthorMultiSelect.vue'
import { useToast } from '../../composables/useToast'

const { showToast } = useToast()

defineProps({
  permissions: { type: Object, default: () => ({}) },
  userContext: { type: Object, default: () => ({}) }
})

const activeTab = ref('today')
const detailIssueId = ref(null)
const syncing = ref(false)
const onlyMine = ref(false)
// При sync меняем refreshKey → дочерние табы остаются (ключ не на корне), но
// мы триггерим reload через emit. Проще — refresh через ref, см. ниже.
const refreshKey = ref(0)

// Поиск — два уровня (input/committed) с применением по Enter/Применить.
// Инициаторы (authorQuery) — массив, multiselect-компонент применяется сразу.
// Табы реагируют через watch на изменение committed-значений (без ремонта,
// чтобы сохранять локальное состояние: дату, страницу, развёрнутые группы).
const searchInput = ref('')
const searchQuery = ref('')
const authorQuery = ref([])

const hasActiveFilters = computed(
  () => Boolean(searchQuery.value) || authorQuery.value.length > 0
)

function applyFilters() {
  searchQuery.value = searchInput.value.trim()
}

function resetFilters() {
  searchInput.value = ''
  searchQuery.value = ''
  authorQuery.value = []
}

const authorOptions = ref([])
async function loadAuthorOptions() {
  try {
    const resp = await fetch('/integrations/okdesk/api/authors/')
    if (!resp.ok) return
    const data = await resp.json()
    authorOptions.value = data.authors || []
  } catch (_) {
    // тихо: автодополнение опционально
  }
}

onMounted(loadAuthorOptions)

function openIssueDetail(issueId) {
  detailIssueId.value = issueId
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) return meta.content
  // Fallback: cookie
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}

// Sync запускается асинхронно: backend кладёт задачи в Celery и возвращает
// task_id'ы. Мы опрашиваем /sync-status/ до их завершения. Это нужно, чтобы
// долгий внешний вызов Okdesk API не блокировал ASGI-worker.
const SYNC_POLL_INTERVAL_MS = 2000
const SYNC_POLL_TIMEOUT_MS = 30 * 60 * 1000 // 30 минут

function fmtTaskResults(tasks) {
  const issues = tasks.issues?.result || {}
  const comments = tasks.comments?.result || {}
  const parts = []
  if (tasks.issues) {
    parts.push(`Заявок: создано ${issues.created || 0}, обновлено ${issues.updated || 0}`)
  }
  if (tasks.comments) {
    parts.push(`Комментариев: создано ${comments.comments_created || 0}, обновлено ${comments.comments_updated || 0}`)
  }
  return parts.join('. ') || 'Готово'
}

async function syncNow() {
  if (syncing.value) return
  syncing.value = true
  try {
    const resp = await fetch('/integrations/okdesk/sync-now/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ issues: true, comments: true }),
    })
    if (resp.status === 409) {
      showToast('Синхронизация уже идёт', 'Подождите её завершения.', 'warning')
      return
    }
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`)
    }
    const data = await resp.json()
    const ids = Object.values(data.tasks || {}).filter(Boolean)
    if (ids.length === 0) {
      throw new Error('Сервер не вернул task_id')
    }

    const idsParam = ids.join(',')
    const started = Date.now()
    while (Date.now() - started < SYNC_POLL_TIMEOUT_MS) {
      await new Promise((r) => setTimeout(r, SYNC_POLL_INTERVAL_MS))
      const sresp = await fetch(`/integrations/okdesk/sync-status/?ids=${encodeURIComponent(idsParam)}&release_lock=1`)
      if (!sresp.ok) continue // транзиентная ошибка — попробуем ещё раз
      const sdata = await sresp.json()
      if (sdata.all_done) {
        // По task_id'ам распределим результаты в issues/comments
        const named = {}
        for (const [name, tid] of Object.entries(data.tasks || {})) {
          named[name] = sdata.tasks[tid]
        }
        const failed = Object.values(named).find((t) => t && t.error)
        if (failed) {
          throw new Error(failed.error)
        }
        showToast('Синхронизация завершена', fmtTaskResults(named), 'success')
        refreshKey.value++
        return
      }
    }
    throw new Error('Таймаут ожидания (>30 мин). Проверьте логи Celery.')
  } catch (e) {
    showToast('Ошибка синхронизации', e.message, 'error')
  } finally {
    syncing.value = false
  }
}
</script>

<style scoped>
.okdesk-dashboard-page {
  padding: 0;
}
.nav-tabs .nav-link {
  cursor: pointer;
}
</style>
