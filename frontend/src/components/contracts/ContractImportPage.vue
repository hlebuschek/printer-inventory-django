<template>
  <div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h4 mb-0">Импорт устройств по договору</h1>
      <a href="/contracts/" class="btn btn-outline-secondary btn-sm">К списку устройств</a>
    </div>

    <div v-if="error" class="alert alert-danger" role="alert">
      {{ error }}
      <button type="button" class="btn-close float-end" @click="error = ''"></button>
    </div>

    <div v-if="notice" class="alert alert-info" role="alert">
      {{ notice }}
      <button type="button" class="btn-close float-end" @click="notice = ''"></button>
    </div>

    <!-- ── Шаг 1: выбор статуса и создание сессии ─────────────────────── -->
    <template v-if="!session">
      <div class="card mb-4">
        <div class="card-header">Новая загрузка</div>
        <div class="card-body">
          <p class="text-muted small">
            Шапка таблицы должна стоять первой строкой файла — преамбулу и место для подписей уберите заранее.
            Обязательные колонки: Организация, Город, Адрес, Производитель, Модель, Серийный номер.
          </p>
          <div class="row g-3">
            <div class="col-md-4">
              <label class="form-label">Название загрузки</label>
              <input v-model="newName" type="text" class="form-control" placeholder="Договор 2026, 1-я партия">
            </div>
            <div class="col-md-3">
              <label class="form-label">Статус для загружаемых устройств <span class="text-danger">*</span></label>
              <select v-model="newStatusId" class="form-select">
                <option value="">— выберите статус —</option>
                <option v-for="s in statuses" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label">Подрядчик <span class="text-danger">*</span></label>
              <select v-model="newProviderId" class="form-select">
                <option value="">— выберите подрядчика —</option>
                <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
              <div v-if="selectedProvider" class="form-text">Заявки: {{ selectedProvider.issue_tracker }}</div>
            </div>
            <div class="col-md-2 d-flex align-items-end">
              <button
                class="btn btn-primary w-100"
                :disabled="!newStatusId || !newProviderId || busy"
                @click="createSession"
              >
                Начать
              </button>
            </div>
          </div>
          <p class="text-muted small mb-0 mt-3">
            Все устройства из файлов этой загрузки будут закреплены за выбранным подрядчиком.
            Файлы разных подрядчиков загружайте отдельными загрузками.
          </p>
        </div>
      </div>

      <div v-if="recentSessions.length" class="card">
        <div class="card-header">Недавние загрузки</div>
        <table class="table table-sm mb-0">
          <tbody>
            <tr v-for="s in recentSessions" :key="s.id">
              <td>{{ s.name }}</td>
              <td>
                <span class="badge" :class="s.state === 'applied' ? 'bg-success' : 'bg-secondary'">
                  {{ s.state === 'applied' ? 'Применена' : 'Черновик' }}
                </span>
              </td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-primary" @click="run(() => openSession(s.id))">Открыть</button>
                <button
                  v-if="s.state !== 'applied'"
                  class="btn btn-sm btn-outline-danger ms-1"
                  @click="deleteSession(s.id)"
                >Удалить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ── Шаг 2+: работа с сессией ────────────────────────────────────── -->
    <template v-else>
      <div class="card mb-3">
        <div class="card-body d-flex justify-content-between align-items-center">
          <div>
            <strong>{{ session.name || 'Загрузка №' + session.id }}</strong>
            <span class="badge ms-2" :class="session.state === 'applied' ? 'bg-success' : 'bg-secondary'">
              {{ session.state === 'applied' ? 'Применена' : 'Черновик' }}
            </span>
            <div class="small text-muted">
              Статус устройств: {{ session.target_status }} ·
              подрядчик: {{ session.service_provider || 'не задан' }} ·
              файлов: {{ session.files.length }} ·
              строк: {{ summary.total }}
            </div>
          </div>
          <button class="btn btn-outline-secondary btn-sm" @click="closeSession">К списку загрузок</button>
        </div>
      </div>

      <div v-if="session.state !== 'applied'" class="card mb-3">
        <div class="card-header">Файлы</div>
        <div class="card-body">
          <div class="row g-2 align-items-end">
            <div class="col-md-8">
              <input
                ref="fileInput"
                type="file"
                class="form-control"
                accept=".xlsx,.xls"
                :disabled="uploading"
                @change="onFileChange"
              >
            </div>
            <div class="col-md-4">
              <button class="btn btn-primary w-100" :disabled="!selectedFile || uploading" @click="uploadFile">
                {{ uploading ? 'Разбор файла…' : 'Загрузить и разобрать' }}
              </button>
            </div>
          </div>
          <ul v-if="session.files.length" class="list-group list-group-flush mt-3">
            <li v-for="f in session.files" :key="f.id" class="list-group-item d-flex justify-content-between px-0">
              <span>{{ f.name }}</span>
              <span class="text-muted small">{{ f.rows_total }} строк</span>
            </li>
          </ul>
        </div>
      </div>

      <template v-if="summary.total">
        <div class="row g-2 mb-3">
          <div v-for="code in CLASS_ORDER" :key="code" class="col">
            <div
              class="card h-100 text-center"
              role="button"
              :class="{ 'border-primary': filterClass === code }"
              @click="setFilter(filterClass === code ? '' : code)"
            >
              <div class="card-body py-2">
                <div class="h4 mb-0">{{ summary.counts[code] || 0 }}</div>
                <div class="small text-muted">{{ CLASS_LABELS[code] }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="summary.unknown_organizations.length" class="alert alert-danger">
          <strong>Организации не найдены в справочнике ({{ summary.unknown_organizations.length }}).</strong>
          Исправьте названия в файле или заведите организации в
          <a href="/admin/inventory/organization/" target="_blank">справочнике</a>, затем загрузите файл заново.
          <ul class="mb-0 mt-2">
            <li v-for="name in summary.unknown_organizations" :key="name">{{ name }}</li>
          </ul>
        </div>

        <div v-if="summary.unknown_models.length" class="alert alert-danger">
          <strong>Модели не найдены в справочнике ({{ summary.unknown_models.length }}).</strong>
          Приведите написание к справочнику — иначе появятся дубли моделей.
          <ul class="mb-0 mt-2">
            <li v-for="name in summary.unknown_models" :key="name">{{ name }}</li>
          </ul>
        </div>

        <div v-if="summary.new_cities.length" class="alert alert-warning">
          <strong>Новые города ({{ summary.new_cities.length }}):</strong>
          {{ summary.new_cities.join(', ') }}
          <div v-if="session.state !== 'applied'" class="form-check mt-2">
            <input id="create-cities" v-model="createCities" class="form-check-input" type="checkbox">
            <label class="form-check-label" for="create-cities">Создать эти города при применении</label>
          </div>
        </div>

        <div class="card mb-3">
          <div class="card-header d-flex flex-wrap gap-2 align-items-center">
            <span>Строки</span>
            <input
              v-model="query"
              type="search"
              class="form-control form-control-sm ms-auto"
              style="max-width: 260px"
              placeholder="Серийник или адрес"
              @keyup.enter="setFilter(filterClass)"
            >
            <button class="btn btn-sm btn-outline-secondary" @click="setFilter(filterClass)">Искать</button>
            <template v-if="session.state !== 'applied' && conflictCount">
              <button class="btn btn-sm btn-outline-success" @click="decideAll('apply')">
                Применить все конфликты
              </button>
              <button class="btn btn-sm btn-outline-secondary" @click="decideAll('skip')">
                Пропустить все конфликты
              </button>
            </template>
          </div>
          <div class="card-body p-0">
            <ImportPreviewTable
              :rows="rows"
              :page-info="pageInfo"
              :editable="session.state !== 'applied'"
              @decide="decideRow"
              @page="(p) => run(() => loadPreview(p))"
            />
          </div>
        </div>

        <div v-if="session.state !== 'applied'" class="d-flex align-items-center gap-3 mb-4">
          <button class="btn btn-success" :disabled="!readyToApply || busy" @click="applySession">
            Применить {{ readyToApply }} строк
          </button>
          <span v-if="conflictPending" class="text-warning-emphasis small">
            Не решено конфликтов: {{ conflictPending }} — такие строки применены не будут.
          </span>
        </div>

        <div v-if="applyResult" class="alert alert-success">
          <strong>Импорт применён.</strong>
          Создано: {{ applyResult.created }}, обновлено: {{ applyResult.updated }},
          ошибок: {{ applyResult.failed }} из {{ applyResult.total }}.
          <ul v-if="applyResult.errors && applyResult.errors.length" class="mb-0 mt-2">
            <li v-for="(e, i) in applyResult.errors" :key="i">{{ e }}</li>
          </ul>
        </div>

        <div v-if="session.state === 'applied'" class="card mb-4">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>
              Автозаведение в опрос по GLPI
              <small class="text-muted ms-2">
                устройства с сетевым портом, которых нет в нашем опросе
              </small>
              <small v-if="autopollStuck" class="text-warning ms-2">
                задача всё ещё в очереди — проверьте, что запущен Celery-воркер
              </small>
            </span>
            <div class="d-flex gap-1">
              <button
                class="btn btn-sm btn-outline-primary"
                :disabled="autopollProbing || busy"
                @click="probeAutopoll"
              >
                <span v-if="autopollProbing" class="spinner-border spinner-border-sm me-1"></span>
                {{ autopollProbing ? 'Проверяем в GLPI…' : 'Проверить в GLPI' }}
              </button>
              <button
                v-if="autopoll"
                class="btn btn-sm btn-outline-secondary"
                :disabled="busy"
                @click="run(loadAutopoll)"
              >Обновить</button>
            </div>
          </div>

          <div v-if="autopoll" class="card-body p-0">
            <div class="table-responsive">
              <table class="table table-sm align-middle mb-0">
                <thead class="table-light">
                  <tr>
                    <th style="width: 2rem">
                      <input
                        v-if="canAddPrinter"
                        type="checkbox"
                        class="form-check-input"
                        :checked="allCreatableSelected"
                        :disabled="!creatableCandidates.length"
                        @change="toggleAllCandidates($event.target.checked)"
                      >
                    </th>
                    <th>Серийный номер</th>
                    <th>Организация / модель</th>
                    <th>Статус</th>
                    <th>Данные GLPI</th>
                    <th>Результат</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="c in autopoll.candidates" :key="c.id">
                    <td>
                      <input
                        v-if="c.can_create && canAddPrinter"
                        v-model="selectedCandidates"
                        type="checkbox"
                        class="form-check-input"
                        :value="c.id"
                      >
                    </td>
                    <td><code>{{ c.serial }}</code></td>
                    <td>
                      <div>{{ c.organization }}</div>
                      <small class="text-muted">{{ c.model }}</small>
                    </td>
                    <td><span :class="candidateBadge(c.status)">{{ c.status_display }}</span></td>
                    <td>
                      <template v-if="c.glpi_ip">
                        <code>{{ c.glpi_ip }}</code>
                        <small class="text-muted d-block">
                          {{ c.glpi_counter }} стр., {{ formatDate(c.glpi_date) }}
                        </small>
                      </template>
                      <small v-else class="text-muted">{{ c.error || '—' }}</small>
                    </td>
                    <td>
                      <span v-if="c.printer_id" class="text-success">
                        Принтер заведён<template v-if="c.last_task">, опрос: {{ c.last_task.status }}</template>
                      </span>
                      <span v-else-if="c.verify_message" :class="c.verify_ok ? 'text-success' : 'text-danger'">
                        {{ c.verify_message }}
                      </span>
                    </td>
                    <td class="text-end">
                      <button
                        v-if="!c.printer_id && c.glpi_ip"
                        class="btn btn-sm btn-outline-secondary"
                        :disabled="!!verifyingId"
                        @click="verifyCandidate(c.id)"
                      >
                        <span v-if="verifyingId === c.id" class="spinner-border spinner-border-sm me-1"></span>
                        {{ verifyingId === c.id ? 'Опрашиваем…' : 'Опросить' }}
                      </button>
                      <a
                        v-if="c.printer_id"
                        class="btn btn-sm btn-outline-primary"
                        :href="`/inventory/${c.printer_id}/history/`"
                      >История</a>
                    </td>
                  </tr>
                  <tr v-if="!autopoll.candidates.length">
                    <td colspan="7" class="text-center text-muted py-3">
                      Устройств для автозаведения нет — все сетевые устройства сессии уже опрашиваются
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="autopoll.candidates.length" class="p-2 border-top d-flex align-items-center gap-3">
              <button
                v-if="canAddPrinter"
                class="btn btn-sm btn-success"
                :disabled="!selectedCandidates.length || busy"
                @click="createSelectedPrinters"
              >Завести в опрос ({{ selectedCandidates.length }})</button>
              <small class="text-muted">
                <template v-if="canAddPrinter">
                  Принтер создаётся с IP из GLPI и community «public», опрос запускается сразу.
                </template>
                <template v-else>
                  Нет права на добавление принтеров — заведение в опрос недоступно.
                </template>
              </small>
            </div>
          </div>
        </div>

        <div v-if="session.state === 'applied'" class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>Не найдены в файлах</span>
            <div>
              <button class="btn btn-sm btn-outline-primary" @click="run(() => loadMissing(1))">Показать</button>
              <a
                class="btn btn-sm btn-outline-secondary ms-1"
                :href="`/contracts/api/import/sessions/${session.id}/missing/export/`"
              >Выгрузить в Excel</a>
            </div>
          </div>
          <div v-if="missing" class="card-body p-0">
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead class="table-light">
                  <tr>
                    <th>Организация</th>
                    <th>Город / адрес</th>
                    <th>Модель</th>
                    <th>Серийный номер</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in missing.rows" :key="d.id">
                    <td>{{ d.organization }}</td>
                    <td>{{ d.city }}, {{ d.address }}<template v-if="d.room">, каб. {{ d.room }}</template></td>
                    <td>{{ d.model }}</td>
                    <td><code>{{ d.serial }}</code></td>
                    <td>{{ d.status }}</td>
                  </tr>
                  <tr v-if="!missing.rows.length">
                    <td colspan="5" class="text-center text-muted py-3">Все устройства организаций сессии есть в файлах</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <nav v-if="missing.page_info.pages > 1" class="p-2">
              <ul class="pagination pagination-sm mb-0 justify-content-center">
                <li class="page-item" :class="{ disabled: missing.page_info.page <= 1 }">
                  <button class="page-link" @click="run(() => loadMissing(missing.page_info.page - 1))">Назад</button>
                </li>
                <li class="page-item disabled">
                  <span class="page-link">
                    {{ missing.page_info.page }} из {{ missing.page_info.pages }} ({{ missing.page_info.total }})
                  </span>
                </li>
                <li class="page-item" :class="{ disabled: missing.page_info.page >= missing.page_info.pages }">
                  <button class="page-link" @click="run(() => loadMissing(missing.page_info.page + 1))">Вперёд</button>
                </li>
              </ul>
            </nav>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import ImportPreviewTable from './ImportPreviewTable.vue'
import { CLASS_LABELS, CLASS_ORDER, CONFLICT_CLASSES } from './importConstants'

const props = defineProps({
  initialData: { type: Object, default: () => ({}) },
  permissions: { type: Object, default: () => ({}) }
})

const canAddPrinter = computed(() => !!props.permissions.add_printer)

const BASE = '/contracts/api/import/sessions/'

const statuses = ref(props.initialData.statuses || [])
const providers = ref(props.initialData.providers || [])
const recentSessions = ref(props.initialData.recent_sessions || [])

const newName = ref('')
const newStatusId = ref('')
const newProviderId = ref('')
const selectedProvider = computed(() => providers.value.find((p) => p.id === Number(newProviderId.value)))

const session = ref(null)
const summary = ref(emptySummary())
const rows = ref([])
const pageInfo = ref({ page: 1, pages: 1, total: 0 })
const readyToApply = ref(0)

const filterClass = ref('')
const query = ref('')
const createCities = ref(false)
const applyResult = ref(null)
const missing = ref(null)

const autopoll = ref(null)
const autopollTaskId = ref('')
const autopollProbing = ref(false)
const autopollWaited = ref(0)
const verifyingId = ref(null)
const verifyTaskId = ref('')
const verifyWaited = ref(0)
const selectedCandidates = ref([])

const selectedFile = ref(null)
const fileInput = ref(null)
const uploading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

const conflictCount = computed(() =>
  CONFLICT_CLASSES.reduce((sum, code) => sum + (summary.value.counts[code] || 0), 0)
)
const conflictPending = computed(() => summary.value.pending_conflicts || 0)

const creatableCandidates = computed(() => (autopoll.value?.candidates || []).filter((c) => c.can_create))
const allCreatableSelected = computed(
  () => creatableCandidates.value.length > 0 && selectedCandidates.value.length === creatableCandidates.value.length
)
const autopollStuck = computed(() => autopollProbing.value && autopollWaited.value >= PROBE_HINT_MS)

function emptySummary() {
  return {
    counts: {},
    total: 0,
    pending_conflicts: 0,
    unknown_organizations: [],
    unknown_models: [],
    new_cities: []
  }
}

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) return meta.content
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

async function request(url, options = {}) {
  const headers = { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
  let body = options.body
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }

  const response = await fetch(url, { ...options, headers, body })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error || `Ошибка сервера: ${response.status}`)
  }
  return data
}

async function run(fn) {
  error.value = ''
  busy.value = true
  try {
    await fn()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function createSession() {
  run(async () => {
    const data = await request(BASE, {
      method: 'POST',
      body: {
        name: newName.value,
        target_status_id: Number(newStatusId.value),
        service_provider_id: Number(newProviderId.value)
      }
    })
    await openSession(data.session_id)
  })
}

async function openSession(id) {
  applyResult.value = null
  missing.value = null
  resetAutopoll()
  filterClass.value = ''
  query.value = ''
  await loadPreview(1, id)
  if (session.value.state === 'applied') {
    // Пустой результат прячем: сессию могли ни разу не проверять в GLPI
    const data = await loadAutopoll()
    if (!data.candidates.length) autopoll.value = null
  }
}

function closeSession() {
  session.value = null
  summary.value = emptySummary()
  rows.value = []
  readyToApply.value = 0
  resetAutopoll()
}

function resetAutopoll() {
  autopoll.value = null
  autopollTaskId.value = ''
  autopollProbing.value = false
  selectedCandidates.value = []
  stopVerify()
}

function deleteSession(id) {
  run(async () => {
    await request(`${BASE}${id}/`, { method: 'DELETE' })
    recentSessions.value = recentSessions.value.filter((s) => s.id !== id)
  })
}

async function loadPreview(page = 1, sessionId = null) {
  const params = new URLSearchParams({ page: String(page) })
  if (filterClass.value) params.set('classification', filterClass.value)
  if (query.value) params.set('q', query.value)

  const data = await request(`${BASE}${sessionId || session.value.id}/preview/?${params}`)
  session.value = data.session
  summary.value = data.summary
  rows.value = data.rows
  pageInfo.value = data.page_info
  readyToApply.value = data.ready_to_apply
}

function setFilter(code) {
  filterClass.value = code
  run(() => loadPreview(1))
}

function onFileChange(event) {
  selectedFile.value = event.target.files[0] || null
}

function uploadFile() {
  uploading.value = true
  error.value = ''
  notice.value = ''
  const body = new FormData()
  body.append('file', selectedFile.value)

  request(`${BASE}${session.value.id}/files/`, { method: 'POST', body })
    .then((data) => {
      if (data.replaced) {
        notice.value = `Файл «${data.original_name}» уже был в загрузке — прежние строки заменены новыми.`
      }
      selectedFile.value = null
      if (fileInput.value) fileInput.value.value = ''
      return loadPreview(1)
    })
    .catch((err) => {
      error.value = err.message
    })
    .finally(() => {
      uploading.value = false
    })
}

function decideRow(rowId, decision) {
  run(async () => {
    await request(`${BASE}${session.value.id}/decisions/`, {
      method: 'POST',
      body: { decisions: [{ row_id: rowId, decision }] }
    })
    await loadPreview(pageInfo.value.page)
  })
}

function decideAll(decision) {
  run(async () => {
    await request(`${BASE}${session.value.id}/decisions/`, {
      method: 'POST',
      body: { all_conflicts: decision }
    })
    await loadPreview(pageInfo.value.page)
  })
}

function applySession() {
  run(async () => {
    applyResult.value = await request(`${BASE}${session.value.id}/apply/`, {
      method: 'POST',
      body: { create_cities: createCities.value }
    })
    await loadPreview(1)
    await loadMissing(1)
  })
}

async function loadMissing(page = 1) {
  missing.value = await request(`${BASE}${session.value.id}/missing/?page=${page}`)
}

// ─── Автозаведение в опрос ──────────────────────────────────────────────────

const CANDIDATE_BADGES = {
  glpi_active: 'badge bg-success',
  glpi_stale: 'badge bg-warning text-dark',
  not_found: 'badge bg-secondary',
  no_ip: 'badge bg-secondary',
  ip_conflict: 'badge bg-danger',
  error: 'badge bg-danger'
}

function candidateBadge(status) {
  return CANDIDATE_BADGES[status] || 'badge bg-secondary'
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function probeAutopoll() {
  run(async () => {
    const data = await request(`${BASE}${session.value.id}/autopoll/probe/`, { method: 'POST' })
    autopollTaskId.value = data.task_id
    autopollProbing.value = true
    autopollWaited.value = 0
    scheduleAutopollPoll()
  })
}

async function fetchAutopoll(taskId) {
  const data = await request(`${BASE}${session.value.id}/autopoll/${taskId ? `?task_id=${taskId}` : ''}`)
  autopoll.value = data
  selectedCandidates.value = selectedCandidates.value.filter((id) =>
    data.candidates.some((c) => c.id === id && c.can_create)
  )
  return data
}

async function loadAutopoll() {
  const data = await fetchAutopoll(autopollTaskId.value)

  if (data.task && data.task.ready) {
    autopollProbing.value = false
    autopollTaskId.value = ''
    autopollWaited.value = 0
    if (data.task.error) error.value = data.task.error
  }
  return data
}

const PROBE_POLL_MS = 2000
// Пока воркер не взял задачу, Celery отдаёт PENDING — отличить «в очереди» от «нет воркера» нельзя,
// поэтому через минуту подсказываем, а через 10 минут перестаём опрашивать.
const PROBE_HINT_MS = 60000
const PROBE_GIVE_UP_MS = 600000

function scheduleAutopollPoll() {
  setTimeout(async () => {
    if (!session.value || !autopollProbing.value) return
    try {
      await loadAutopoll()
    } catch (err) {
      error.value = err.message
      autopollProbing.value = false
      return
    }
    if (!autopollProbing.value) return
    autopollWaited.value += PROBE_POLL_MS
    if (autopollWaited.value >= PROBE_GIVE_UP_MS) {
      autopollProbing.value = false
      autopollTaskId.value = ''
      error.value = 'Проверка в GLPI не завершилась за 10 минут. Задача осталась в очереди — нажмите «Обновить» позже.'
      return
    }
    scheduleAutopollPoll()
  }, PROBE_POLL_MS)
}

function toggleAllCandidates(checked) {
  selectedCandidates.value = checked ? creatableCandidates.value.map((c) => c.id) : []
}

async function verifyCandidate(candidateId) {
  // Не через run(): опрос идёт в Celery и тянется до полутора минут, глобальный busy
  // на это время погасил бы все кнопки страницы.
  error.value = ''
  verifyingId.value = candidateId
  verifyWaited.value = 0
  try {
    const data = await request(`${BASE}${session.value.id}/autopoll/${candidateId}/verify/`, { method: 'POST' })
    verifyTaskId.value = data.task_id
    scheduleVerifyPoll()
  } catch (err) {
    error.value = err.message
    verifyingId.value = null
  }
}

function scheduleVerifyPoll() {
  setTimeout(async () => {
    if (!session.value || !verifyingId.value) return
    let data
    try {
      data = await fetchAutopoll(verifyTaskId.value)
    } catch (err) {
      error.value = err.message
      stopVerify()
      return
    }

    if (data.task && data.task.ready) {
      if (data.task.error) error.value = data.task.error
      stopVerify()
      return
    }

    verifyWaited.value += PROBE_POLL_MS
    if (verifyWaited.value >= PROBE_GIVE_UP_MS) {
      error.value = 'Пробный опрос не завершился за 10 минут. Задача осталась в очереди — нажмите «Обновить» позже.'
      stopVerify()
      return
    }
    scheduleVerifyPoll()
  }, PROBE_POLL_MS)
}

function stopVerify() {
  verifyingId.value = null
  verifyTaskId.value = ''
  verifyWaited.value = 0
}

function createSelectedPrinters() {
  run(async () => {
    const data = await request(`${BASE}${session.value.id}/autopoll/create/`, {
      method: 'POST',
      body: { candidate_ids: selectedCandidates.value }
    })
    const failed = data.results.filter((r) => !r.created)
    notice.value = failed.length
      ? `Заведено ${data.created}, не удалось ${failed.length}: ${failed.map((r) => `${r.serial} — ${r.error}`).join('; ')}`
      : `Заведено принтеров: ${data.created}. Опрос запущен, обновите список через минуту.`
    await loadAutopoll()
  })
}
</script>
