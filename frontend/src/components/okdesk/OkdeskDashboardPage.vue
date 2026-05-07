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
    </ul>

    <div v-if="activeTab === 'today'">
      <OkdeskTodayTab
        :key="`today-${refreshKey}-${onlyMine}`"
        :only-mine="onlyMine"
        @open-issue="openIssueDetail"
      />
    </div>

    <div v-else-if="activeTab === 'active'">
      <OkdeskActiveTab
        :key="`active-${refreshKey}-${onlyMine}`"
        :only-mine="onlyMine"
        @open-issue="openIssueDetail"
      />
    </div>

    <div v-else-if="activeTab === 'closed'">
      <OkdeskClosedTab
        :key="`closed-${refreshKey}-${onlyMine}`"
        :only-mine="onlyMine"
        @open-issue="openIssueDetail"
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
import { ref } from 'vue'
import ToastContainer from '../common/ToastContainer.vue'
import OkdeskTodayTab from './OkdeskTodayTab.vue'
import OkdeskActiveTab from './OkdeskActiveTab.vue'
import OkdeskClosedTab from './OkdeskClosedTab.vue'
import OkdeskIssueDetailModal from './OkdeskIssueDetailModal.vue'
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
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`)
    }
    const data = await resp.json()
    const issues = data.issues || {}
    const comments = data.comments || {}
    const summary = [
      `Заявок: создано ${issues.created || 0}, обновлено ${issues.updated || 0}`,
      `Комментариев: создано ${comments.comments_created || 0}, обновлено ${comments.comments_updated || 0}`,
    ].join('. ')
    showToast('Синхронизация завершена', summary, 'success')
    // Триггерим перезагрузку активного таба
    refreshKey.value++
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
