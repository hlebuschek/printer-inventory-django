<template>
  <div
    v-if="open"
    class="modal-backdrop-custom"
    @click.self="$emit('close')"
  >
    <div class="modal-dialog-custom card shadow-lg">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0">
          <i class="bi bi-file-earmark-excel me-1"></i>
          Экспорт {{ scopeLabel }}
        </h5>
        <button
          type="button"
          class="btn-close"
          aria-label="Закрыть"
          @click="$emit('close')"
        ></button>
      </div>

      <div class="card-body">
        <p class="text-muted small mb-3">
          Что выгрузить в XLSX?
        </p>

        <div class="d-grid gap-2">
          <button
            type="button"
            class="btn btn-success text-start d-flex align-items-center gap-2"
            :disabled="!hasFilters"
            @click="downloadFiltered"
          >
            <i class="bi bi-funnel-fill fs-5"></i>
            <div class="flex-grow-1">
              <div class="fw-semibold">С учётом текущих фильтров</div>
              <div class="small text-white-50">
                <template v-if="hasFilters">
                  Заявок в выборке: <strong>{{ filteredCount }}</strong>
                </template>
                <template v-else>
                  Фильтры не применены — этот вариант недоступен
                </template>
              </div>
            </div>
          </button>

          <button
            type="button"
            class="btn btn-outline-success text-start d-flex align-items-center gap-2"
            @click="downloadAll"
          >
            <i class="bi bi-archive fs-5"></i>
            <div class="flex-grow-1">
              <div class="fw-semibold">Все заявки</div>
              <div class="small text-muted">
                Без применения фильтров (q, инициатор, период, «только мои»)
              </div>
            </div>
          </button>
        </div>

        <div v-if="hasFilters" class="mt-3 small">
          <div class="text-muted mb-1">Активные фильтры:</div>
          <div class="d-flex flex-wrap gap-1">
            <span v-if="filters.q" class="badge text-bg-light border">
              поиск: {{ filters.q }}
            </span>
            <span v-if="filters.authors?.length" class="badge text-bg-light border">
              инициаторов: {{ filters.authors.length }}
            </span>
            <span v-if="filters.mine" class="badge text-bg-light border">
              только мои
            </span>
            <span v-if="filters.date_from || filters.date_to" class="badge text-bg-light border">
              период: {{ filters.date_from || '…' }} – {{ filters.date_to || '…' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  // 'active' | 'closed'
  scope: { type: String, required: true },
  filters: { type: Object, default: () => ({}) },
  filteredCount: { type: Number, default: 0 }
})
defineEmits(['close'])

const scopeLabel = computed(() =>
  props.scope === 'closed' ? 'закрытых заявок' : 'активных заявок'
)

const endpoint = computed(() =>
  props.scope === 'closed'
    ? '/integrations/okdesk/export/closed-filtered/'
    : '/integrations/okdesk/export/active-filtered/'
)

const hasFilters = computed(() => {
  const f = props.filters || {}
  return Boolean(
    f.q ||
    (f.authors && f.authors.length) ||
    f.mine ||
    f.date_from ||
    f.date_to
  )
})

function buildFilteredUrl() {
  const params = new URLSearchParams()
  const f = props.filters || {}
  if (f.q) params.set('q', f.q)
  for (const a of f.authors || []) params.append('author', a)
  if (f.mine) params.set('mine', 'true')
  if (f.date_from) params.set('date_from', f.date_from)
  if (f.date_to) params.set('date_to', f.date_to)
  return `${endpoint.value}?${params.toString()}`
}

function triggerDownload(url) {
  // Скачивание через временный <a download>: страница не уходит в навигацию,
  // браузер сам подхватит Content-Disposition: attachment.
  const link = document.createElement('a')
  link.href = url
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function downloadFiltered() {
  triggerDownload(buildFilteredUrl())
}

function downloadAll() {
  triggerDownload(endpoint.value)
}
</script>

<style scoped>
.modal-backdrop-custom {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1080;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.modal-dialog-custom {
  width: 100%;
  max-width: 520px;
}
</style>
