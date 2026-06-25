<template>
  <Teleport to="body">
    <div v-if="show" class="modal fade show d-block" tabindex="-1" @click.self="onBackdrop">
      <div class="modal-dialog modal-dialog-centered modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title d-flex align-items-center gap-2">
              <i class="bi bi-file-earmark-excel text-success"></i>
              Выгрузка статистики устройств
            </h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <div class="modal-body">
            <!-- Параметры -->
            <div v-if="!running && !done" class="row g-3 mb-3">
              <div class="col-sm-6">
                <label class="form-label small">Молчащие принтеры за период</label>
                <select v-model.number="days" class="form-select form-select-sm">
                  <option :value="7">7 дней</option>
                  <option :value="14">14 дней</option>
                  <option :value="30">30 дней</option>
                </select>
              </div>
              <div class="col-sm-6">
                <label class="form-label small">Объём печати за период</label>
                <select v-model.number="months" class="form-select form-select-sm">
                  <option :value="0">Всё время</option>
                  <option :value="6">6 месяцев</option>
                  <option :value="12">12 месяцев</option>
                </select>
              </div>
              <div class="col-12 small text-muted">
                <i class="bi bi-info-circle"></i>
                Отчёт собирается в фоне. Можно следить за прогрессом ниже.
              </div>
            </div>

            <!-- Прогресс -->
            <div v-if="running || done">
              <div class="d-flex justify-content-between small mb-1">
                <span>{{ message }}</span>
                <span class="fw-semibold">{{ percent }}%</span>
              </div>
              <div class="progress mb-3" style="height: 10px;">
                <div
                  class="progress-bar"
                  :class="errorMsg ? 'bg-danger' : (done ? 'bg-success' : 'progress-bar-striped progress-bar-animated bg-primary')"
                  role="progressbar"
                  :style="`width: ${percent}%`"
                ></div>
              </div>

              <div ref="logBox" class="log-box border rounded bg-body-tertiary p-2 font-monospace small">
                <div v-for="(line, i) in log" :key="i">{{ line }}</div>
                <div v-if="!log.length" class="text-muted">Ожидание запуска…</div>
              </div>

              <div v-if="errorMsg" class="alert alert-danger small mt-3 mb-0">
                <i class="bi bi-exclamation-triangle"></i> {{ errorMsg }}
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button v-if="!running && !done" type="button" class="btn btn-secondary btn-sm" @click="close">
              Отмена
            </button>
            <button v-if="!running && !done" type="button" class="btn btn-success btn-sm" @click="start">
              <i class="bi bi-play-fill"></i> Запустить выгрузку
            </button>

            <template v-if="running">
              <button type="button" class="btn btn-secondary btn-sm" disabled>
                <span class="spinner-border spinner-border-sm me-1"></span> Выполняется…
              </button>
              <button type="button" class="btn btn-outline-secondary btn-sm" @click="close">
                Закрыть
              </button>
            </template>

            <template v-if="done">
              <button type="button" class="btn btn-secondary btn-sm" @click="reset">
                Новая выгрузка
              </button>
              <button
                v-if="!errorMsg && downloadUrl"
                type="button"
                class="btn btn-success btn-sm"
                @click="download"
              >
                <i class="bi bi-download"></i> Скачать файл
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>
    <div v-if="show" class="modal-backdrop fade show"></div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { fetchApi } from '../../utils/api.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  orgId: { type: Number, default: null },
})
const emit = defineEmits(['close'])

const days = ref(7)
const months = ref(0)

const running = ref(false)
const done = ref(false)
const percent = ref(0)
const message = ref('')
const log = ref([])
const errorMsg = ref('')
const downloadUrl = ref('')
const logBox = ref(null)

let pollTimer = null

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function reset() {
  stopPolling()
  running.value = false
  done.value = false
  percent.value = 0
  message.value = ''
  log.value = []
  errorMsg.value = ''
  downloadUrl.value = ''
}

async function scrollLog() {
  await nextTick()
  if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
}

async function start() {
  reset()
  running.value = true
  message.value = 'Постановка задачи…'

  const params = new URLSearchParams({ days: days.value, months: months.value })
  if (props.orgId) params.set('org', props.orgId)

  let res
  try {
    res = await fetchApi(`/dashboard/api/statistics-export/start/?${params}`, { method: 'POST' })
  } catch (e) {
    running.value = false
    done.value = true
    errorMsg.value = 'Не удалось запустить выгрузку'
    return
  }
  if (!res.ok || !res.task_id) {
    running.value = false
    done.value = true
    errorMsg.value = res.error || 'Не удалось запустить выгрузку'
    return
  }

  pollStatus(res.status_url)
}

function pollStatus(statusUrl) {
  stopPolling()
  pollTimer = setInterval(async () => {
    let res
    try {
      res = await fetchApi(statusUrl)
    } catch (e) {
      return // временная ошибка сети — продолжаем опрос
    }
    if (!res.ok) return
    const s = res.data
    percent.value = s.percent ?? percent.value
    message.value = s.message || message.value
    if (Array.isArray(s.log)) {
      log.value = s.log
      scrollLog()
    }
    if (s.done) {
      stopPolling()
      running.value = false
      done.value = true
      if (s.error) {
        errorMsg.value = s.error
      } else {
        downloadUrl.value = s.download_url || ''
      }
    }
  }, 1000)
}

function download() {
  if (downloadUrl.value) window.location.href = downloadUrl.value
}

function close() {
  stopPolling()
  emit('close')
}

function onBackdrop() {
  close()
}

// Сброс при закрытии модалки
watch(() => props.show, (v) => {
  if (!v) reset()
})

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.log-box {
  height: 180px;
  overflow-y: auto;
  white-space: pre-wrap;
}
</style>
