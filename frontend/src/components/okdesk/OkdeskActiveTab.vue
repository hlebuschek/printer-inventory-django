<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div class="text-muted small">
        Всего активных заявок: <span class="fw-semibold">{{ totalActive }}</span>
      </div>
      <a
        class="btn btn-success btn-sm"
        href="/integrations/okdesk/export/active-all/"
        title="Excel со всеми активными по листам на каждый статус"
      >
        <i class="bi bi-file-earmark-excel"></i> Все активные · XLSX
      </a>
    </div>

    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else-if="!groups.length" class="text-center text-muted py-5">
      Нет активных заявок.
    </div>

    <div v-else class="row row-cols-1 row-cols-md-2 g-3">
      <div v-for="g in groups" :key="g.status" class="col">
        <div class="card shadow-sm h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span class="fw-semibold">{{ g.status }}</span>
            <span class="badge text-bg-primary">{{ g.count }}</span>
          </div>

          <ul v-if="g.samples?.length" class="list-group list-group-flush">
            <button
              v-for="issue in (expanded[g.status] ? fullList[g.status] || g.samples : g.samples)"
              :key="issue.issue_id"
              class="list-group-item list-group-item-action text-start"
              type="button"
              @click="$emit('open-issue', issue.issue_id)"
            >
              <div class="d-flex justify-content-between gap-2">
                <div class="flex-grow-1 min-w-0">
                  <div class="fw-semibold text-truncate">
                    <span class="text-muted me-1">#{{ issue.issue_id }}</span>
                    {{ issue.title || 'Без темы' }}
                  </div>
                  <div class="small text-muted text-truncate">
                    {{ issue.organization || issue.company_name || '—' }}
                    <span v-if="issue.serial_number" class="ms-2">
                      <i class="bi bi-upc-scan"></i> {{ issue.serial_number }}
                    </span>
                  </div>
                </div>
                <div class="text-end small text-nowrap">
                  <span v-if="issue.is_overdue" class="badge text-bg-danger d-block mb-1">
                    Просрочена
                  </span>
                  <span class="text-muted">{{ formatDate(issue.created_at) }}</span>
                </div>
              </div>
            </button>
          </ul>

          <div v-if="g.count > g.samples.length" class="card-footer d-flex justify-content-between gap-2">
            <button
              class="btn btn-link btn-sm p-0"
              @click="loadFull(g.status)"
              :disabled="loadingStatus === g.status"
            >
              <span v-if="!expanded[g.status]">
                Показать все {{ g.count }}
                <i class="bi bi-chevron-down"></i>
              </span>
              <span v-else>
                Скрыть
                <i class="bi bi-chevron-up"></i>
              </span>
            </button>
            <a
              class="btn btn-outline-success btn-sm"
              :href="`/integrations/okdesk/export/by-status/${encodeURIComponent(g.status)}/`"
              title="Экспорт этого статуса в Excel"
            >
              <i class="bi bi-file-earmark-excel"></i>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useToast } from '../../composables/useToast'

const { showToast } = useToast()

const props = defineProps({
  onlyMine: { type: Boolean, default: false }
})
defineEmits(['open-issue'])

const groups = ref([])
const loading = ref(false)
const loadingStatus = ref(null)
const expanded = ref({})
const fullList = ref({})

const totalActive = computed(() => groups.value.reduce((acc, g) => acc + g.count, 0))

function buildParams(extra = {}) {
  const params = new URLSearchParams(extra)
  if (props.onlyMine) params.set('mine', 'true')
  return params
}

async function loadGroups() {
  loading.value = true
  try {
    const resp = await fetch(`/integrations/okdesk/api/active-grouped/?${buildParams()}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    groups.value = data.groups || []
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить активные: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function loadFull(status) {
  if (expanded.value[status]) {
    expanded.value[status] = false
    return
  }
  if (fullList.value[status]) {
    expanded.value[status] = true
    return
  }
  loadingStatus.value = status
  try {
    const resp = await fetch(
      `/integrations/okdesk/api/by-status/${encodeURIComponent(status)}/?${buildParams({ page: 1 })}`
    )
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    fullList.value[status] = data.issues || []
    expanded.value[status] = true
  } catch (e) {
    showToast('Ошибка', `Не удалось загрузить заявки: ${e.message}`, 'error')
  } finally {
    loadingStatus.value = null
  }
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch { return '' }
}

onMounted(loadGroups)
</script>

<style scoped>
.min-w-0 { min-width: 0; }
</style>
