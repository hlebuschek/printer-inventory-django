<template>
  <div class="container-fluid py-3" v-if="group">
    <ToastContainer />
    <div class="d-flex align-items-center mb-3 flex-wrap gap-2">
      <a href="/supplies-report/" class="btn btn-link btn-sm p-0 me-2">
        <i class="bi bi-arrow-left"></i> К списку
      </a>
      <h1 class="h4 mb-0 d-flex align-items-center gap-2 flex-grow-1">
        <i class="bi bi-droplet-half"></i> {{ group.name }}
      </h1>
      <button
        v-if="canManage && group.is_active"
        class="btn btn-outline-success"
        :disabled="sendingNow"
        @click="sendNow"
        title="Отправить через SMTP (см. EMAIL_BACKEND в settings)"
      >
        <span v-if="sendingNow" class="spinner-border spinner-border-sm me-1"></span>
        <i v-else class="bi bi-send"></i> Отправить сейчас
      </button>
      <a
        v-if="canDownload && group.is_active"
        :href="`/supplies-report/${group.id}/download.eml`"
        class="btn btn-success"
        title="Скачать .eml — откроется в Outlook как черновик"
      >
        <i class="bi bi-envelope-arrow-up"></i> Скачать .eml
      </a>
    </div>

    <!-- Settings card -->
    <div class="card mb-3">
      <div class="card-header py-2 d-flex align-items-center gap-2 cursor-pointer" @click="settingsOpen = !settingsOpen">
        <i class="bi" :class="settingsOpen ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
        <span class="fw-semibold">Настройки письма</span>
        <span class="text-muted small ms-2">{{ savedSettingsLabel }}</span>
      </div>
      <div v-show="settingsOpen" class="card-body">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Название группы</label>
            <input
              v-model="form.name"
              class="form-control"
              :disabled="!canManage"
              @change="saveGroup(['name'])"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Локация (в теме письма)</label>
            <input
              v-model="form.location_label"
              class="form-control"
              :disabled="!canManage"
              @change="saveGroup(['location_label'])"
            />
          </div>
          <div class="col-md-12">
            <label class="form-label small text-muted mb-1">Шаблон темы</label>
            <input
              v-model="form.subject_template"
              class="form-control font-monospace"
              :disabled="!canManage"
              @change="saveGroup(['subject_template'])"
            />
            <div class="form-text">Плейсхолдеры: <code>{date}</code> (дд.мм.гггг), <code>{location}</code></div>
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Получатели To (через запятую/перенос строки)</label>
            <textarea
              v-model="form.to_emails"
              class="form-control"
              rows="2"
              :disabled="!canManage"
              @change="saveGroup(['to_emails'])"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Получатели Cc</label>
            <textarea
              v-model="form.cc_emails"
              class="form-control"
              rows="2"
              :disabled="!canManage"
              @change="saveGroup(['cc_emails'])"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Адрес отправителя (необязательно)</label>
            <input
              v-model="form.from_email"
              type="email"
              class="form-control"
              placeholder="по умолчанию — email текущего пользователя"
              :disabled="!canManage"
              @change="saveGroup(['from_email'])"
            />
          </div>
          <div class="col-md-3">
            <label class="form-label small text-muted mb-1">Порог устаревания (часов)</label>
            <input
              v-model.number="form.stale_threshold_hours"
              type="number"
              min="1"
              class="form-control"
              :disabled="!canManage"
              @change="saveGroup(['stale_threshold_hours'])"
            />
          </div>
          <div class="col-md-3 d-flex align-items-end">
            <div class="form-check form-switch">
              <input
                v-model="form.is_active"
                id="grp-active"
                type="checkbox"
                class="form-check-input"
                :disabled="!canManage"
                @change="saveGroup(['is_active'])"
              />
              <label for="grp-active" class="form-check-label">Группа активна</label>
            </div>
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Вступление письма</label>
            <textarea
              v-model="form.body_intro"
              class="form-control"
              rows="3"
              :disabled="!canManage"
              @change="saveGroup(['body_intro'])"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Подпись</label>
            <textarea
              v-model="form.body_signature"
              class="form-control"
              rows="3"
              :disabled="!canManage"
              @change="saveGroup(['body_signature'])"
            />
          </div>
        </div>

        <hr class="my-3">
        <h6 class="text-muted mb-3"><i class="bi bi-clock-history"></i> Автоотправка по расписанию</h6>
        <div class="row g-3">
          <div class="col-md-3 d-flex align-items-end">
            <div class="form-check form-switch">
              <input
                v-model="form.auto_send_enabled"
                id="grp-auto-send"
                type="checkbox"
                class="form-check-input"
                :disabled="!canManage"
                @change="saveGroup(['auto_send_enabled'])"
              />
              <label for="grp-auto-send" class="form-check-label">Автоотправка</label>
            </div>
          </div>
          <div class="col-md-3">
            <label class="form-label small text-muted mb-1">Время</label>
            <input
              v-model="form.auto_send_time"
              type="time"
              class="form-control"
              :disabled="!canManage || !form.auto_send_enabled"
              @change="saveGroup(['auto_send_time'])"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label small text-muted mb-1">Дни недели</label>
            <div class="d-flex gap-2 flex-wrap">
              <div
                v-for="d in weekdayOptions"
                :key="d.value"
                class="form-check"
              >
                <input
                  :id="`wd-${d.value}`"
                  type="checkbox"
                  class="form-check-input"
                  :value="d.value"
                  :checked="selectedWeekdays.includes(d.value)"
                  :disabled="!canManage || !form.auto_send_enabled"
                  @change="toggleWeekday(d.value, $event.target.checked)"
                />
                <label :for="`wd-${d.value}`" class="form-check-label small">{{ d.label }}</label>
              </div>
            </div>
          </div>
          <div class="col-md-12">
            <div class="d-flex gap-3 small text-muted flex-wrap">
              <span v-if="group.last_sent_at">
                <i class="bi bi-check-circle text-success"></i>
                Последняя отправка: <strong>{{ formatDate(group.last_sent_at) }}</strong>
              </span>
              <span v-else class="text-muted">Ещё не отправлялось.</span>
              <span v-if="group.last_send_error" class="text-danger">
                <i class="bi bi-exclamation-triangle"></i> Последняя ошибка: {{ group.last_send_error }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Items table (editable) -->
    <div class="card mb-3">
      <div class="card-header d-flex align-items-center gap-2">
        <span class="fw-semibold">Принтеры в письме</span>
        <span class="badge text-bg-secondary">{{ items.length }}</span>
        <div class="ms-auto d-flex gap-2">
          <button
            v-if="canManage"
            class="btn btn-sm btn-outline-primary"
            @click="openAddForm"
          >
            <i class="bi bi-plus-lg"></i> Добавить принтер
          </button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th style="width:60px;">№</th>
              <th style="width:140px;">IP</th>
              <th>Модель</th>
              <th style="min-width:220px;">Расположение</th>
              <th style="min-width:220px;">Дополнительно</th>
              <th style="width:50px;"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="addOpen">
              <td>
                <input v-model.number="addForm.sort_order" type="number" class="form-control form-control-sm" />
              </td>
              <td colspan="2">
                <div class="position-relative">
                  <input
                    v-model="addForm.printer_query"
                    type="text"
                    class="form-control form-control-sm"
                    placeholder="IP или серийник…"
                    @input="searchPrinters"
                  />
                  <ul
                    v-if="addSearchResults.length"
                    class="list-group position-absolute w-100"
                    style="z-index:5; max-height:240px; overflow:auto;"
                  >
                    <li
                      v-for="p in addSearchResults"
                      :key="p.id"
                      class="list-group-item list-group-item-action small"
                      style="cursor:pointer;"
                      @click="pickPrinter(p)"
                    >
                      <span class="fw-semibold">{{ p.ip_address }}</span> · {{ p.model }} · {{ p.serial_number }}
                    </li>
                  </ul>
                  <div v-if="addForm.selected" class="form-text">
                    Выбран: <strong>{{ addForm.selected.ip_address }}</strong> · {{ addForm.selected.model }}
                  </div>
                </div>
              </td>
              <td>
                <textarea v-model="addForm.location" class="form-control form-control-sm" rows="2" placeholder="5 этаж&#10;каб. 157.1" />
              </td>
              <td>
                <textarea v-model="addForm.additional_info" class="form-control form-control-sm" rows="2" placeholder="ФИО, примечание" />
              </td>
              <td class="text-end">
                <div class="d-flex flex-column gap-1">
                  <button class="btn btn-sm btn-success" :disabled="!addForm.selected" @click="submitAdd">
                    <i class="bi bi-check"></i> Добавить
                  </button>
                  <button class="btn btn-sm btn-outline-secondary" @click="cancelAdd">Отмена</button>
                </div>
              </td>
            </tr>

            <tr v-for="item in items" :key="item.id">
              <td>
                <EditableField
                  :model-value="item.sort_order"
                  type="number"
                  :disabled="!canManage"
                  :save-fn="(val) => saveItemField(item, 'sort_order', val)"
                />
              </td>
              <td class="font-monospace">{{ item.printer.ip_address }}</td>
              <td>
                <span>{{ item.printer.model || '—' }}</span>
                <div class="small text-muted">{{ item.printer.serial_number }}</div>
              </td>
              <td>
                <EditableField
                  :model-value="item.location"
                  type="textarea"
                  :rows="2"
                  :disabled="!canManage"
                  :save-fn="(val) => saveItemField(item, 'location', val)"
                />
              </td>
              <td>
                <EditableField
                  :model-value="item.additional_info"
                  type="textarea"
                  :rows="2"
                  :disabled="!canManage"
                  :save-fn="(val) => saveItemField(item, 'additional_info', val)"
                />
              </td>
              <td class="text-end">
                <button
                  v-if="canManage"
                  class="btn btn-sm btn-outline-danger"
                  title="Убрать из группы"
                  @click="deleteItem(item)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
            <tr v-if="!items.length && !addOpen">
              <td colspan="6" class="text-muted text-center py-3">Пока ни одного принтера. Нажмите «Добавить принтер».</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Preview of the email content -->
    <div class="card mb-3">
      <div class="card-header py-2 d-flex align-items-center gap-2 cursor-pointer" @click="previewOpen = !previewOpen">
        <i class="bi" :class="previewOpen ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
        <span class="fw-semibold">Предпросмотр данных письма</span>
        <span class="text-muted small ms-2">{{ rows.length }} строк</span>
        <button
          v-if="previewOpen"
          class="btn btn-link btn-sm ms-auto p-0"
          @click.stop="reloadPreview"
          title="Обновить — взять свежие данные опросов"
        >
          <i class="bi bi-arrow-clockwise"></i> Обновить
        </button>
      </div>
      <div v-show="previewOpen" class="card-body p-0">
        <table class="table table-bordered table-sm mb-0">
          <thead class="table-light">
            <tr>
              <th>IP&nbsp;Адрес</th>
              <th>Наименование</th>
              <th>Расположение</th>
              <th>Дополнительно</th>
              <th>Цвет</th>
              <th colspan="2">Остаток, %</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="row.item_id">
              <tr v-if="!row.consumables.length">
                <td>{{ row.ip }}</td>
                <td>{{ row.model }}</td>
                <td><div class="preserve-newlines">{{ row.location || '—' }}</div><StaleNote :row="row" /></td>
                <td><div class="preserve-newlines">{{ row.additional_info || '—' }}</div></td>
                <td colspan="3" class="text-muted">—</td>
              </tr>
              <tr v-for="(c, idx) in row.consumables" :key="`${row.item_id}-${c.label}`">
                <td v-if="idx === 0" :rowspan="row.consumables.length">{{ row.ip }}</td>
                <td v-if="idx === 0" :rowspan="row.consumables.length">{{ row.model }}</td>
                <td v-if="idx === 0" :rowspan="row.consumables.length">
                  <div class="preserve-newlines">{{ row.location || '—' }}</div>
                  <StaleNote :row="row" />
                </td>
                <td v-if="idx === 0" :rowspan="row.consumables.length">
                  <div class="preserve-newlines">{{ row.additional_info || '—' }}</div>
                </td>
                <td>{{ c.label }}</td>
                <td class="fw-semibold">{{ c.toner || '—' }}</td>
                <td class="fw-semibold">{{ c.drum || '—' }}</td>
              </tr>
            </template>
            <tr v-if="!rows.length">
              <td colspan="7" class="text-muted text-center py-3">Нет данных.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div v-else-if="loading" class="container-fluid py-5 text-center text-muted">
    <div class="spinner-border spinner-border-sm me-2"></div> Загрузка…
  </div>
  <div v-else class="container-fluid py-5 text-danger">
    Не удалось загрузить группу.
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, h } from 'vue'
import EditableField from './EditableField.vue'
import ToastContainer from '../common/ToastContainer.vue'
import { useToast } from '../../composables/useToast'

const { showToast } = useToast()

const mountEl = document.getElementById('supplies-report-group-page')
const groupId = parseInt(mountEl?.dataset?.groupId || '0', 10)
const canManage = mountEl?.dataset?.canManage === '1'
const canDownload = mountEl?.dataset?.canDownload === '1'

const loading = ref(true)
const group = ref(null)
const items = ref([])
const rows = ref([])

const settingsOpen = ref(false)
const previewOpen = ref(true)
const lastSavedAt = ref(null)

const form = reactive({
  name: '',
  location_label: '',
  subject_template: '',
  body_intro: '',
  body_signature: '',
  from_email: '',
  to_emails: '',
  cc_emails: '',
  stale_threshold_hours: 24,
  is_active: true,
  auto_send_enabled: false,
  auto_send_time: '',
  auto_send_weekdays: '1,2,3,4,5',
})

const weekdayOptions = [
  { value: 1, label: 'Пн' },
  { value: 2, label: 'Вт' },
  { value: 3, label: 'Ср' },
  { value: 4, label: 'Чт' },
  { value: 5, label: 'Пт' },
  { value: 6, label: 'Сб' },
  { value: 7, label: 'Вс' },
]

const sendingNow = ref(false)

const selectedWeekdays = computed(() =>
  (form.auto_send_weekdays || '')
    .split(',')
    .map(s => parseInt(s.trim(), 10))
    .filter(n => !isNaN(n))
)

function toggleWeekday(value, checked) {
  const set = new Set(selectedWeekdays.value)
  if (checked) set.add(value)
  else set.delete(value)
  form.auto_send_weekdays = Array.from(set).sort().join(',')
  saveGroup(['auto_send_weekdays'])
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const addOpen = ref(false)
const addForm = reactive({
  printer_query: '',
  selected: null,
  location: '',
  additional_info: '',
  sort_order: null,
})
const addSearchResults = ref([])

const savedSettingsLabel = computed(() =>
  lastSavedAt.value ? `сохранено в ${lastSavedAt.value}` : ''
)

// Inline component для пометки stale
const StaleNote = (props) => {
  const row = props.row
  if (row.no_data) {
    return h('div', { class: 'small text-danger fst-italic' }, 'нет данных опроса')
  }
  if (row.is_stale && row.last_polled_at) {
    const d = new Date(row.last_polled_at)
    const txt = `данные от ${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    return h('div', { class: 'small text-danger fst-italic' }, txt)
  }
  return null
}
StaleNote.props = ['row']
function pad(n) { return String(n).padStart(2, '0') }

function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return m ? m.pop() : ''
}

function fillForm(g) {
  form.name = g.name || ''
  form.location_label = g.location_label || ''
  form.subject_template = g.subject_template || ''
  form.body_intro = g.body_intro || ''
  form.body_signature = g.body_signature || ''
  form.from_email = g.from_email || ''
  form.to_emails = g.to_emails || ''
  form.cc_emails = g.cc_emails || ''
  form.stale_threshold_hours = g.stale_threshold_hours || 24
  form.is_active = !!g.is_active
  form.auto_send_enabled = !!g.auto_send_enabled
  form.auto_send_time = g.auto_send_time || ''
  form.auto_send_weekdays = g.auto_send_weekdays || '1,2,3,4,5'
}

async function sendNow() {
  if (!canManage) return
  if (!confirm('Отправить письмо прямо сейчас по адресам из настроек?')) return
  sendingNow.value = true
  try {
    const r = await fetch(`/supplies-report/api/groups/${groupId}/send-now/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    })
    if (!r.ok) {
      // Сервер может отдавать JSON-ошибку (например, 503 от недоступного брокера).
      let errMsg
      try {
        const data = await r.json()
        errMsg = data.error || JSON.stringify(data)
      } catch {
        errMsg = (await r.text()) || `HTTP ${r.status}`
      }
      throw new Error(errMsg)
    }
    showToast('Отправка', 'Задача поставлена в очередь. Статус обновится через несколько секунд.', 'success')
    // Подтянем статус через 3 секунды — task_id из ответа можно потом завести в polling.
    setTimeout(loadAll, 3000)
  } catch (e) {
    console.error(e)
    showToast('Ошибка', 'Не удалось запустить отправку: ' + e.message, 'error')
  } finally {
    sendingNow.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    const r = await fetch(`/supplies-report/api/groups/${groupId}/`)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const data = await r.json()
    group.value = data.group
    items.value = data.items
    rows.value = data.rows
    fillForm(data.group)
  } catch (e) {
    console.error('Ошибка загрузки:', e)
  } finally {
    loading.value = false
  }
}

async function reloadPreview() {
  try {
    const r = await fetch(`/supplies-report/api/groups/${groupId}/`)
    if (!r.ok) return
    const data = await r.json()
    rows.value = data.rows
  } catch (e) {
    console.error(e)
  }
}

async function saveGroup(fields) {
  if (!canManage) return
  const payload = {}
  for (const f of fields) payload[f] = form[f]
  try {
    const r = await fetch(`/supplies-report/api/groups/${groupId}/update/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify(payload),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const data = await r.json()
    group.value = data.group
    lastSavedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    console.error('Не удалось сохранить:', e)
    showToast('Ошибка', 'Не удалось сохранить изменения. Подробности в консоли.', 'error')
  }
}

async function saveItemField(item, field, value) {
  if (!canManage) throw new Error('no permission')
  const patch = { [field]: value }
  const r = await fetch(`/supplies-report/api/items/${item.id}/`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(patch),
  })
  if (!r.ok) {
    const txt = await r.text()
    throw new Error(txt || `HTTP ${r.status}`)
  }
  const data = await r.json()
  // Не подменяем целиком объект — внутрь edit'ов не лезем, чтобы анимация не сбросилась.
  // Локально обновим поля item, на случай если бэк подправил значение.
  Object.assign(item, data.item)
  // Если меняли sort_order — пересортируем
  if (field === 'sort_order') {
    items.value.sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
  }
  // Превью обновим тихо в фоне
  reloadPreview().catch(() => {})
}

async function deleteItem(item) {
  if (!canManage) return
  if (!confirm(`Убрать ${item.printer.ip_address} из группы?`)) return
  try {
    const r = await fetch(`/supplies-report/api/items/${item.id}/delete/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    items.value = items.value.filter(i => i.id !== item.id)
    await reloadPreview()
  } catch (e) {
    console.error(e)
    showToast('Ошибка', 'Не удалось удалить строку.', 'error')
  }
}

function openAddForm() {
  addOpen.value = true
  addForm.printer_query = ''
  addForm.selected = null
  addForm.location = ''
  addForm.additional_info = ''
  addForm.sort_order = items.value.length
    ? Math.max(...items.value.map(i => i.sort_order)) + 1
    : 1
  addSearchResults.value = []
}

function cancelAdd() {
  addOpen.value = false
  addSearchResults.value = []
}

let searchTimer = null
function searchPrinters() {
  addForm.selected = null
  clearTimeout(searchTimer)
  const q = addForm.printer_query.trim()
  if (q.length < 2) {
    addSearchResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const r = await fetch(`/supplies-report/api/printers/search/?q=${encodeURIComponent(q)}`)
      if (!r.ok) return
      const data = await r.json()
      addSearchResults.value = data.results || []
    } catch (e) {
      console.error(e)
    }
  }, 250)
}

function pickPrinter(p) {
  addForm.selected = p
  addForm.printer_query = `${p.ip_address} · ${p.model}`
  addSearchResults.value = []
}

async function submitAdd() {
  if (!addForm.selected) return
  try {
    const r = await fetch(`/supplies-report/api/groups/${groupId}/items/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({
        printer_id: addForm.selected.id,
        sort_order: addForm.sort_order,
        location: addForm.location,
        additional_info: addForm.additional_info,
      }),
    })
    if (!r.ok) {
      const txt = await r.text()
      throw new Error(txt || `HTTP ${r.status}`)
    }
    const data = await r.json()
    items.value.push(data.item)
    items.value.sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
    cancelAdd()
    await reloadPreview()
  } catch (e) {
    console.error(e)
    showToast('Ошибка', 'Не удалось добавить принтер: ' + e.message, 'error')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.cursor-pointer { cursor: pointer; }
.preserve-newlines { white-space: pre-line; }
</style>
