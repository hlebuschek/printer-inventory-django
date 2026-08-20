<template>
  <div class="border-start border-4 rounded bg-light p-2 mb-3" :class="isOutgoing ? 'border-primary' : 'border-success'">
    <div class="d-flex justify-content-between small text-muted">
      <span>{{ senderLabel }}</span>
      <span>{{ formatDateTime(message.sent_at) }}</span>
    </div>

    <div v-if="message.subject || message.channel === 'email'" class="fw-semibold small">
      {{ message.subject || 'Без темы' }}
    </div>
    <template v-if="requestTable">
      <table class="table table-sm table-bordered bg-white small mb-2 mt-1">
        <tbody>
          <tr v-for="row in requestTable.rows" :key="row.name">
            <th class="text-nowrap fw-semibold">{{ row.name }}</th>
            <td>{{ row.value }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="requestTable.rest" class="small message-body text-muted">{{ requestTable.rest }}</div>
    </template>
    <div v-else-if="message.body_text" class="small message-body">{{ message.body_text }}</div>

    <div v-if="imageAttachments.length" class="d-flex flex-wrap gap-2 mt-1">
      <a
        v-for="attachment in imageAttachments"
        :key="attachment.id"
        :href="fileUrl(attachment)"
        target="_blank"
        rel="noopener"
        class="attachment-thumb"
        :title="`${attachment.filename} (${formatSize(attachment.size)})`"
      >
        <img :src="fileUrl(attachment)" :alt="attachment.filename" loading="lazy" />
      </a>
    </div>
    <div v-for="attachment in fileAttachments" :key="attachment.id" class="small">
      <a v-if="fileUrl(attachment)" :href="fileUrl(attachment)" target="_blank" rel="noopener">
        <i class="bi bi-paperclip me-1"></i>{{ attachment.filename }}
      </a>
      <span v-else class="text-muted">
        <i class="bi bi-paperclip me-1"></i>{{ attachment.filename }}
      </span>
      <span class="text-muted ms-1">({{ formatSize(attachment.size) }})</span>
      <button
        v-if="!fileUrl(attachment) && attachment.can_fetch"
        type="button"
        class="btn btn-link btn-sm p-0 ms-2 align-baseline"
        :disabled="pending[attachment.id]"
        @click="fetchFile(attachment)"
      >
        {{ pending[attachment.id] ? 'Загрузка…' : 'Загрузить из Okdesk' }}
      </button>
      <span v-if="errors[attachment.id]" class="text-danger ms-2">{{ errors[attachment.id] }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { fetchApi } from '../../utils/api'

const props = defineProps({
  message: { type: Object, required: true }
})

// Ссылки на докачанные файлы держим отдельно: message приходит пропсом и правится списком
const downloaded = reactive({})
const pending = reactive({})
const errors = reactive({})

function fileUrl(attachment) {
  return downloaded[attachment.id] || attachment.url
}

async function fetchFile(attachment) {
  pending[attachment.id] = true
  delete errors[attachment.id]
  try {
    const data = await fetchApi(`/contracts/api/requests/attachments/${attachment.id}/fetch/`, { method: 'POST' })
    downloaded[attachment.id] = data.url
  } catch (e) {
    errors[attachment.id] = e.status === 502 ? 'Хранилище Okdesk недоступно' : 'Не удалось загрузить файл'
  } finally {
    pending[attachment.id] = false
  }
}

const isOutgoing = computed(() => props.message.direction === 'out')

const senderLabel = computed(() => {
  if (!isOutgoing.value) return props.message.from_email
  if (props.message.to_emails) return `Мы → ${props.message.to_emails}`
  // Okdesk-комментарий нашего сотрудника: адресата нет, но автор известен
  return props.message.from_email ? `${props.message.from_email} (мы)` : 'Мы'
})

const IMAGE_EXT = /\.(jpe?g|png|gif|webp|bmp|heic)$/i

function isImage(attachment) {
  return (attachment.content_type || '').startsWith('image/') || IMAGE_EXT.test(attachment.filename || '')
}

// Картинка без скачанного файла показывается строкой с кнопкой, а не битой миниатюрой
const imageAttachments = computed(() => (props.message.attachments || []).filter((a) => isImage(a) && fileUrl(a)))
const fileAttachments = computed(() => (props.message.attachments || []).filter((a) => !isImage(a) || !fileUrl(a)))

// Текстовая версия нашего письма-заявки — список «Ключ: значение» (см. build_description);
// собираем её обратно в таблицу, как в HTML-версии письма у подрядчика
const REQUEST_KEYS = new Set([
  '№ заявки', 'Организация', 'Город', 'Адрес', 'Кабинет', 'Производитель',
  'Модель', 'Серийный номер', 'Картридж', 'Ремонт/обслуживание', 'Комментарии',
])

const requestTable = computed(() => {
  const body = props.message.body_text
  if (!isOutgoing.value || !body || !body.startsWith('№ заявки: ')) return null
  const lines = body.split('\n')
  const rows = []
  let i = 0
  for (; i < lines.length; i++) {
    const line = lines[i]
    if (!line.trim()) break
    const m = line.match(/^([^:]+): (.*)$/)
    if (m && REQUEST_KEYS.has(m[1])) {
      rows.push({ name: m[1], value: m[2] })
    } else if (rows.length) {
      rows[rows.length - 1].value += '\n' + line
    }
  }
  if (rows.length < 3) return null
  return { rows, rest: lines.slice(i).join('\n').trim() }
})

function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}
</script>

<style scoped>
/* Переносы строк из письма значимы: подрядчик пишет списками и подписью в столбик */
.message-body {
  white-space: pre-wrap;
}

.attachment-thumb img {
  max-width: 160px;
  max-height: 120px;
  object-fit: cover;
  border-radius: 0.375rem;
  border: 1px solid var(--bs-border-color);
}
</style>
