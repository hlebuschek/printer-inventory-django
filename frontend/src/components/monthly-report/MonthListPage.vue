<template>
  <div class="month-list-page">
    <!-- Toast Container -->
    <ToastContainer />

    <h1 class="h4 mb-3">Ежемесячные отчёты</h1>

    <div class="d-flex flex-wrap align-items-center month-toolbar mb-3">
      <div class="input-group input-group-sm" style="max-width: 340px;">
        <span class="input-group-text"><i class="bi bi-search"></i></span>
        <input
          v-model="searchQuery"
          type="text"
          class="form-control"
          placeholder="Поиск: ноябрь, 2025, Иркутск..."
        />
      </div>

      <div class="input-group input-group-sm" style="width: 220px;">
        <span class="input-group-text"><i class="bi bi-filter"></i></span>
        <select v-model="selectedYear" class="form-select">
          <option value="">Все годы</option>
          <option v-for="year in availableYears" :key="year" :value="year">
            {{ year }}
          </option>
        </select>
      </div>

      <div class="ms-auto d-flex align-items-center small text-muted">
        <span>{{ visibleCount }} из {{ months.length }}</span>
      </div>

      <a
        v-if="permissions.upload_monthly_report"
        class="btn btn-success btn-sm ms-2"
        href="/monthly-report/upload/"
      >
        <i class="bi bi-file-earmark-excel"></i> Загрузка Excel
      </a>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <!-- Months grid -->
    <div v-else class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 g-3">
      <div
        v-for="month in filteredMonths"
        :key="month.month_str"
        class="col month-item"
      >
        <div class="month-card-wrapper">
          <a :href="`/monthly-report/${month.month_str}/`" class="text-decoration-none">
            <div class="card shadow-sm month-card h-100" :class="{ 'unpublished': !month.is_published && permissions.manage_months }">
              <div class="card-body d-flex flex-column">
                <div class="d-flex align-items-start justify-content-between mb-3">
                  <div class="flex-grow-1">
                    <div class="text-muted small mb-1">{{ month.year }}</div>
                    <h5 class="card-title mb-2">{{ month.month_name }}</h5>
                    <!-- Статус публикации -->
                    <div v-if="permissions.manage_months">
                      <span
                        v-if="!month.is_published"
                        class="badge bg-warning text-dark"
                        title="Месяц виден только администраторам"
                      >
                        <i class="bi bi-eye-slash-fill"></i> Скрыт
                      </span>
                      <span
                        v-else
                        class="badge bg-success"
                        title="Месяц виден всем пользователям"
                      >
                        <i class="bi bi-check-circle-fill"></i> Опубликован
                      </span>
                    </div>
                  </div>

                  <div class="text-end">
                    <div class="month-count">{{ month.count }}</div>
                    <div class="small text-muted">записей</div>
                  </div>
                </div>

                <div v-if="month.is_editable" class="mt-auto mb-3">
                  <div class="alert alert-success p-2 mb-0 small">
                    <i class="bi bi-unlock-fill"></i> Редактирование до {{ month.edit_until }}
                  </div>
                </div>

                <div class="mt-auto pt-3 border-top">
                  <div class="d-flex align-items-center justify-content-between text-primary">
                    <span class="small fw-medium">Открыть отчёт</span>
                    <i class="bi bi-arrow-right-circle-fill"></i>
                  </div>
                </div>
              </div>
            </div>
          </a>

          <!-- Action buttons (outside clickable card) -->
          <div class="month-actions mt-2">
            <div class="d-grid gap-2">
              <!-- Toggle publish button -->
              <button
                v-if="permissions.manage_months"
                class="btn btn-sm publish-btn"
                :class="month.is_published ? 'btn-warning' : 'btn-success'"
                :title="month.is_published ? 'Скрыть месяц от пользователей' : 'Опубликовать месяц для всех'"
                @click="togglePublished(month)"
              >
                <i :class="month.is_published ? 'bi bi-eye-slash-fill' : 'bi bi-eye-fill'"></i>
                {{ month.is_published ? 'Скрыть от пользователей' : 'Опубликовать для всех' }}
              </button>

              <!-- Export button -->
              <a
                :href="`/monthly-report/${month.year}/${month.month_number}/export-excel/`"
                class="btn btn-sm btn-outline-primary"
                title="Скачать Excel"
              >
                <i class="bi bi-download"></i> Скачать Excel
              </a>
            </div>
          </div>
        </div>
      </div>

      <div v-if="filteredMonths.length === 0" class="col">
        <div class="alert alert-secondary mb-0">
          {{ months.length === 0 ? 'Нет загруженных месяцев.' : 'Нет результатов по вашему запросу.' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useUrlFilters } from '../../composables/useUrlFilters'
import { useToast } from '../../composables/useToast'
import ToastContainer from '../common/ToastContainer.vue'

const { showToast } = useToast()

const months = ref([])
const loading = ref(true)
const permissions = ref({})

// Filters для синхронизации с URL
const filters = reactive({
  q: '',
  year: ''
})

// URL filters
const { loadFiltersFromUrl, saveFiltersToUrl, clearFiltersFromUrl } = useUrlFilters(filters, () => {
  // Callback вызывается при popstate (кнопки назад/вперед)
  // Просто обновляем computed свойства через реактивность
})

// Refs для v-model (синхронизированы с filters)
const searchQuery = computed({
  get: () => filters.q,
  set: (value) => {
    filters.q = value
    saveFiltersToUrl(true) // replace для плавной работы
  }
})

const selectedYear = computed({
  get: () => filters.year,
  set: (value) => {
    filters.year = value
    saveFiltersToUrl(true) // replace для плавной работы
  }
})

// Computed properties
const availableYears = computed(() => {
  const years = [...new Set(months.value.map(m => m.year))]
  return years.sort((a, b) => b - a)
})

const filteredMonths = computed(() => {
  let result = months.value

  // Filter by year
  if (filters.year) {
    result = result.filter(m => m.year.toString() === filters.year.toString())
  }

  // Filter by search query
  if (filters.q.trim()) {
    const query = filters.q.trim().toLowerCase()
    result = result.filter(m => {
      const searchText = `${m.month_name} ${m.year}`.toLowerCase()
      return searchText.includes(query)
    })
  }

  return result
})

const visibleCount = computed(() => filteredMonths.value.length)

// Fetch months data
async function fetchMonths() {
  loading.value = true
  try {
    const response = await fetch('/monthly-report/api/months/')
    const data = await response.json()

    if (data.ok) {
      months.value = data.months
      permissions.value = data.permissions || {}
    }
  } catch (error) {
    console.error('Error loading months:', error)
  } finally {
    loading.value = false
  }
}

// Toggle month published status
async function togglePublished(month) {
  const newStatus = !month.is_published
  const action = newStatus ? 'опубликовать' : 'скрыть'

  if (!confirm(`Вы уверены, что хотите ${action} месяц ${month.month_name} ${month.year}?`)) {
    return
  }

  try {
    const response = await fetch('/monthly-report/api/toggle-month-published/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        year: month.year,
        month: month.month_number,
        is_published: newStatus
      })
    })

    const data = await response.json()

    if (data.success) {
      // Обновляем статус месяца в списке
      month.is_published = newStatus

      showToast(
        'Успешно',
        data.message || `Месяц ${newStatus ? 'опубликован' : 'скрыт'}`,
        'success'
      )
    } else {
      showToast(
        'Ошибка',
        data.error || 'Не удалось изменить статус публикации',
        'error'
      )
    }
  } catch (error) {
    console.error('Error toggling month published status:', error)
    showToast(
      'Ошибка',
      'Не удалось изменить статус публикации',
      'error'
    )
  }
}

// Get CSRF token from cookie
function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return ''
}

onMounted(() => {
  // Загружаем фильтры из URL
  loadFiltersFromUrl()
  fetchMonths()
})
</script>

<style scoped>
.month-toolbar {
  gap: 0.5rem;
}

.month-card-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.month-card-wrapper > a {
  flex: 1;
  display: flex;
}

.month-card {
  transition: all 0.2s ease;
  border-radius: 0.75rem;
  border: 2px solid transparent;
}

.month-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.1);
  border-color: rgba(13, 110, 253, 0.2);
}

.month-card.unpublished {
  border-left: 4px solid #ffc107;
  background: linear-gradient(to right, rgba(255, 193, 7, 0.05), transparent);
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #212529;
  margin-bottom: 0;
}

.month-count {
  font-size: 2rem;
  font-weight: 700;
  color: #0d6efd;
  line-height: 1;
}

.badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
}

.badge.bg-warning {
  background-color: #ffc107 !important;
}

.badge.bg-success {
  background-color: #198754 !important;
  color: white !important;
}

.alert-success {
  background-color: rgba(25, 135, 84, 0.1);
  border-color: rgba(25, 135, 84, 0.2);
  color: #0f5132;
  font-size: 0.875rem;
}

/* Action buttons */
.month-actions {
  opacity: 0;
  transition: opacity 0.2s ease;
}

.month-card-wrapper:hover .month-actions {
  opacity: 1;
}

.publish-btn {
  font-weight: 600;
  transition: all 0.15s ease;
}

.publish-btn.btn-success {
  background-color: #198754;
  border-color: #198754;
  color: white;
}

.publish-btn.btn-success:hover {
  background-color: #157347;
  border-color: #146c43;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(25, 135, 84, 0.3);
}

.publish-btn.btn-warning {
  background-color: #ffc107;
  border-color: #ffc107;
  color: #000;
}

.publish-btn.btn-warning:hover {
  background-color: #ffca2c;
  border-color: #ffc720;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(255, 193, 7, 0.3);
}

.btn-outline-primary {
  transition: all 0.15s ease;
}

.btn-outline-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(13, 110, 253, 0.3);
}
</style>
