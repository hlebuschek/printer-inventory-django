<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="modal fade show d-block"
      tabindex="-1"
      role="dialog"
      @click.self="close"
    >
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <span class="text-muted me-2">#{{ issueId }}</span>
              {{ issue?.title || (loading ? 'Загрузка...' : 'Заявка') }}
            </h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <div class="modal-body">
            <div v-if="loading" class="text-center py-5">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
              </div>
            </div>

            <div v-else-if="!issue" class="text-center text-muted py-5">
              Заявка не найдена.
            </div>

            <div v-else>
              <!-- Шапка: статус, приоритет, даты, исполнитель -->
              <div class="row g-2 mb-3">
                <div class="col-12 col-md-4">
                  <div class="text-muted small">Статус</div>
                  <span class="badge" :class="statusBadgeClass(issue.status_name)">
                    {{ issue.status_name || '—' }}
                  </span>
                </div>
                <div class="col-12 col-md-4">
                  <div class="text-muted small">Приоритет</div>
                  <div>{{ issue.priority_name || '—' }}</div>
                </div>
                <div class="col-12 col-md-4">
                  <div class="text-muted small">Исполнитель</div>
                  <div>{{ issue.assignee_name || '—' }}</div>
                </div>

                <div class="col-12 col-md-4">
                  <div class="text-muted small">Создана</div>
                  <div>{{ formatDateTime(issue.created_at) }}</div>
                </div>
                <div class="col-12 col-md-4">
                  <div class="text-muted small">Дедлайн</div>
                  <div>
                    {{ formatDateTime(issue.deadline_at) }}
                    <span v-if="issue.is_overdue" class="badge text-bg-danger ms-2">
                      Просрочена
                    </span>
                  </div>
                </div>
                <div class="col-12 col-md-4">
                  <div class="text-muted small">Завершена</div>
                  <div>{{ formatDateTime(issue.completed_at) }}</div>
                </div>

                <div class="col-12 col-md-6">
                  <div class="text-muted small">Автор</div>
                  <div>{{ issue.author_name || '—' }}</div>
                </div>
                <div class="col-12 col-md-6">
                  <div class="text-muted small">Компания</div>
                  <div>{{ issue.company_name || issue.organization || '—' }}</div>
                </div>
              </div>

              <!-- Привязанные устройства -->
              <div v-if="issue.devices?.length" class="mb-3">
                <div class="text-muted small mb-1">Устройства из договора</div>
                <ul class="list-group list-group-flush devices-list">
                  <li
                    v-for="d in issue.devices"
                    :key="d.contract_device_id"
                    class="list-group-item d-flex justify-content-between gap-2"
                  >
                    <div>
                      <div class="fw-semibold">{{ d.serial_number || '—' }}</div>
                      <div class="small text-muted">
                        {{ d.organization || '—' }} · {{ d.address || '—' }}
                      </div>
                    </div>
                    <div class="small text-muted text-end">{{ d.model || '' }}</div>
                  </li>
                </ul>
              </div>

              <div v-else-if="issue.serial_numbers" class="mb-3">
                <div class="text-muted small mb-1">Серийные номера (без привязки)</div>
                <code class="d-block text-wrap">{{ issue.serial_numbers }}</code>
              </div>

              <!-- Комментарии -->
              <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="fw-semibold">
                  <i class="bi bi-chat-left-text"></i>
                  Комментарии
                  <span class="text-muted">({{ issue.comments?.length || 0 }})</span>
                </div>
                <button
                  type="button"
                  class="btn btn-link btn-sm py-0 px-1"
                  :disabled="refreshing"
                  @click="refreshComments"
                  title="Обновить комментарии из Okdesk"
                >
                  <span
                    v-if="refreshing"
                    class="spinner-border spinner-border-sm"
                    role="status"
                  ></span>
                  <i v-else class="bi bi-arrow-clockwise"></i>
                </button>
              </div>

              <div v-if="!issue.comments?.length" class="text-muted small mb-3">
                Комментариев пока нет.
              </div>

              <ul v-else class="list-unstyled comment-list mb-3">
                <li
                  v-for="c in issue.comments"
                  :key="c.id"
                  class="comment-item"
                  :class="{ 'comment-private': !c.is_public }"
                >
                  <div class="d-flex justify-content-between mb-1">
                    <div class="fw-semibold">
                      {{ c.author || 'Без автора' }}
                      <span
                        v-if="!c.is_public"
                        class="badge bg-secondary-subtle text-secondary-emphasis ms-1"
                      >приватный</span>
                    </div>
                    <small class="text-muted">{{ formatDateTime(c.created_at) }}</small>
                  </div>
                  <div class="comment-content" v-html="renderContent(c.content)"></div>
                </li>
              </ul>

              <!-- Форма ответа -->
              <div v-if="canPost" class="reply-form p-3">
                <label class="form-label small fw-semibold">
                  Ответить
                  <span v-if="userContext?.okdesk_name" class="text-muted fw-normal">
                    (от имени {{ userContext.okdesk_name }})
                  </span>
                </label>
                <textarea
                  v-model="replyContent"
                  class="form-control"
                  rows="3"
                  placeholder="Введите комментарий..."
                  :disabled="posting"
                ></textarea>
                <div class="d-flex justify-content-between align-items-center mt-2">
                  <div class="form-check form-switch">
                    <input
                      id="reply-private"
                      v-model="replyIsPrivate"
                      class="form-check-input"
                      type="checkbox"
                      :disabled="posting"
                    />
                    <label class="form-check-label small" for="reply-private">
                      Приватный (виден только сотрудникам)
                    </label>
                  </div>
                  <button
                    type="button"
                    class="btn btn-primary btn-sm"
                    :disabled="posting || !replyContent.trim()"
                    @click="submitReply"
                  >
                    <span
                      v-if="posting"
                      class="spinner-border spinner-border-sm me-1"
                      role="status"
                    ></span>
                    <i v-else class="bi bi-send"></i>
                    Отправить
                  </button>
                </div>
              </div>

              <div
                v-else-if="permissions?.post_okdesk_comment && !userContext?.has_okdesk_token"
                class="alert alert-warning small mb-0"
              >
                <i class="bi bi-exclamation-triangle"></i>
                Для отправки комментариев нужен личный API-токен Okdesk.
                Добавьте его в меню пользователя → «Токен Okdesk».
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="close">
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="show" class="modal-backdrop fade show"></div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useToast } from '../../composables/useToast'

const { showToast } = useToast()

const props = defineProps({
  issueId: { type: [Number, null], default: null },
  permissions: { type: Object, default: () => ({}) },
  userContext: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:issue-id'])

const issue = ref(null)
const loading = ref(false)
const refreshing = ref(false)
const posting = ref(false)
const replyContent = ref('')
const replyIsPrivate = ref(false)

const show = computed(() => props.issueId !== null)
const canPost = computed(
  () => props.permissions?.post_okdesk_comment && props.userContext?.has_okdesk_token
)

watch(() => props.issueId, async (newId) => {
  if (newId === null) {
    issue.value = null
    replyContent.value = ''
    replyIsPrivate.value = false
    return
  }
  await load(newId)
  // Lazy refresh — после показа из БД дёрнем Okdesk API за свежими комментами
  refreshComments({ silent: true })
})

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) return meta.content
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}

async function load(id) {
  loading.value = true
  issue.value = null
  try {
    const resp = await fetch(`/integrations/okdesk/api/issue/${id}/`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    issue.value = await resp.json()
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить заявку #${id}: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

// refresh запускается в Celery, фронт опрашивает sync-status и перезагружает
// заявку из БД (Celery-таск к моменту ready уже записал свежие комментарии).
const REFRESH_POLL_INTERVAL_MS = 1500
const REFRESH_POLL_TIMEOUT_MS = 60 * 1000

async function refreshComments({ silent = false } = {}) {
  if (!props.issueId || refreshing.value) return
  const issueIdAtStart = props.issueId
  refreshing.value = true
  try {
    const resp = await fetch(`/integrations/okdesk/api/issue/${issueIdAtStart}/refresh-comments/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    const taskId = data.task_id
    if (!taskId) throw new Error('Сервер не вернул task_id')

    const started = Date.now()
    let taskResult = null
    while (Date.now() - started < REFRESH_POLL_TIMEOUT_MS) {
      await new Promise((r) => setTimeout(r, REFRESH_POLL_INTERVAL_MS))
      // Пользователь успел закрыть модалку / переключиться — прекращаем
      if (props.issueId !== issueIdAtStart) return
      const sresp = await fetch(`/integrations/okdesk/sync-status/?ids=${encodeURIComponent(taskId)}`)
      if (!sresp.ok) continue
      const sdata = await sresp.json()
      if (sdata.all_done) {
        taskResult = sdata.tasks[taskId]
        break
      }
    }
    if (!taskResult) throw new Error('Таймаут обновления комментариев')
    if (taskResult.error) throw new Error(taskResult.error)

    // Celery-таск уже записал свежие комментарии в БД — перезагружаем заявку
    await load(issueIdAtStart)
    const updated = taskResult.result?.updated ?? 0
    if (!silent) showToast('Обновлено', `Подгружено комментариев: ${updated}`, 'success')
  } catch (e) {
    if (!silent) showToast('Ошибка', `Не удалось обновить: ${e.message}`, 'error')
  } finally {
    refreshing.value = false
  }
}

async function submitReply() {
  const text = replyContent.value.trim()
  if (!text || posting.value) return
  posting.value = true
  try {
    const resp = await fetch(`/integrations/okdesk/api/issue/${props.issueId}/comments/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ content: text, is_public: !replyIsPrivate.value }),
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`)
    // Добавляем в список локально (приходит уже от API)
    if (issue.value && data.comment) {
      issue.value.comments = [...(issue.value.comments || []), data.comment]
    }
    replyContent.value = ''
    replyIsPrivate.value = false
    showToast('Комментарий отправлен', 'Опубликован в Okdesk.', 'success')
  } catch (e) {
    showToast('Ошибка отправки', e.message, 'error')
  } finally {
    posting.value = false
  }
}

function close() {
  emit('update:issue-id', null)
}

function statusBadgeClass(status) {
  const map = {
    'Закрыта': 'text-bg-success',
    'Открыта': 'text-bg-primary',
    'В работе': 'text-bg-warning',
    'Требует решения': 'text-bg-danger',
    'Ожидает запчасть': 'text-bg-info',
  }
  return map[status] || 'text-bg-secondary'
}

function formatDateTime(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  } catch { return iso }
}

function renderContent(text) {
  if (!text) return ''
  // Okdesk может присылать HTML (таблицы, форматирование).
  // Извлекаем чистый текст через временный DOM-элемент.
  const temp = document.createElement('div')
  temp.innerHTML = text
  const plainText = temp.textContent || temp.innerText || ''
  // Экранируем результат и преобразуем переносы строк в <br>
  const escaped = plainText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  return escaped.replace(/\n/g, '<br>')
}
</script>

<style scoped>
.comment-list {
  max-height: 50vh;
  overflow-y: auto;
}
.comment-item {
  padding: 0.75rem 0;
  border-top: 1px solid var(--bs-border-color-translucent);
}
.comment-item:first-child {
  border-top: none;
}
.comment-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--bs-body-color);
  text-align: left;
}
.comment-private {
  background: var(--bs-secondary-bg-subtle);
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  border-radius: 6px;
}
.modal {
  background-color: rgba(0, 0, 0, 0.4);
}
.reply-form {
  background: var(--bs-body-tertiary-bg, var(--bs-light));
  border: 1px solid #dee2e6;
  border-radius: 0.375rem;
}
.devices-list {
  border: 1px solid #dee2e6;
  border-radius: 0.375rem;
  background: var(--bs-body-bg);
}
</style>

<style>
/* Unscoped для работы с data-bs-theme */
[data-bs-theme="dark"] .reply-form {
  background: #2b3035 !important;
  border-color: #495057 !important;
}
[data-bs-theme="dark"] .devices-list {
  border-color: #495057 !important;
}
</style>
