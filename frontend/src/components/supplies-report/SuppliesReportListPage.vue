<template>
  <div class="container-fluid py-3">
    <ToastContainer />
    <div class="d-flex align-items-center mb-3">
      <h1 class="h4 mb-0 d-flex align-items-center gap-2">
        <i class="bi bi-droplet-half"></i> Отчёт по расходникам
      </h1>
    </div>

    <div v-if="loading" class="text-center text-muted py-4">
      <div class="spinner-border spinner-border-sm me-2"></div> Загрузка…
    </div>

    <div v-else-if="loadError" class="alert alert-danger d-flex align-items-center gap-2">
      <i class="bi bi-exclamation-triangle"></i>
      <span>Не удалось загрузить список групп: {{ loadError }}</span>
      <button class="btn btn-sm btn-outline-danger ms-auto" @click="loadGroups">Повторить</button>
    </div>

    <div v-else-if="groups.length === 0" class="alert alert-info">
      Нет ни одной группы рассылки. Создайте её в админке Django:
      <a href="/admin/supplies_report/reportgroup/add/">/admin/supplies_report/reportgroup/add/</a>.
    </div>

    <div v-else class="table-responsive">
      <table class="table table-hover align-middle">
        <thead>
          <tr>
            <th>Название</th>
            <th>Локация (в теме)</th>
            <th class="text-end">Принтеров</th>
            <th>Получатели To</th>
            <th>Получатели Cc</th>
            <th>Активна</th>
            <th class="text-end" style="min-width:240px;">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in groups" :key="g.id">
            <td>
              <a :href="`/supplies-report/${g.id}/`" class="fw-semibold text-decoration-none">
                {{ g.name }}
              </a>
            </td>
            <td class="text-muted">{{ g.location_label || '—' }}</td>
            <td class="text-end">{{ g.items_count }}</td>
            <td class="text-muted small" style="max-width:240px;">
              <span v-if="g.to_emails">{{ g.to_emails.split(/[,;\n]+/).filter(Boolean).join(', ') }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-muted small" style="max-width:240px;">
              <span v-if="g.cc_emails">{{ g.cc_emails.split(/[,;\n]+/).filter(Boolean).join(', ') }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <span v-if="g.is_active" class="badge text-bg-success">да</span>
              <span v-else class="badge text-bg-secondary">нет</span>
            </td>
            <td class="text-end">
              <a :href="`/supplies-report/${g.id}/`" class="btn btn-sm btn-outline-primary me-1">
                <i class="bi bi-pencil-square"></i> Открыть
              </a>
              <a
                v-if="canDownload && g.is_active"
                :href="`/supplies-report/${g.id}/download.eml`"
                class="btn btn-sm btn-success"
              >
                <i class="bi bi-envelope-arrow-up"></i> Скачать .eml
              </a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from '../../composables/useToast'
import ToastContainer from '../common/ToastContainer.vue'

const { showToast } = useToast()

const groups = ref([])
const loading = ref(true)
const loadError = ref('')

const mountEl = document.getElementById('supplies-report-list-page')
const canDownload = mountEl?.dataset?.canDownload === '1'

async function loadGroups() {
  loading.value = true
  loadError.value = ''
  try {
    const r = await fetch('/supplies-report/api/groups/')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const data = await r.json()
    groups.value = data.groups || []
  } catch (e) {
    console.error('Не удалось загрузить группы:', e)
    loadError.value = e.message || 'Не удалось загрузить группы'
    showToast('Ошибка', loadError.value, 'error')
  } finally {
    loading.value = false
  }
}

onMounted(loadGroups)
</script>
