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
        <a :href="`/monthly-report/${month.month_str}/`" class="text-decoration-none">
          <div class="card shadow-sm month-card h-100">
            <div class="card-body d-flex flex-column">
              <div class="d-flex align-items-start justify-content-between">
                <div>
                  <div class="text-muted small">{{ month.year }}</div>
                  <div class="fw-semibold">{{ month.month_name }}</div>
                  <!-- Бейдж "Скрыт" для неопубликованных месяцев (только админы видят) -->
                  <div v-if="!month.is_published && permissions.manage_months" class="mt-1">
                    <span class="badge bg-warning-subtle text-warning-emphasis" title="Месяц виден только администраторам">
                      <i class="bi bi-eye-slash"></i> Скрыт
                    </span>
                  </div>
                </div>

                <div class="text-end">
                  <span class="badge bg-primary-subtle text-primary-emphasis month-badge">
                    {{ month.count }} записей
                  </span>
                  <div v-if="month.is_editable" class="small mt-1">
                    <span class="badge bg-success-subtle text-success-emphasis" title="Редактирование открыто">
                      <i class="bi bi-unlock"></i> до {{ month.edit_until }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Метрики заполненности и пользователей -->
              <div class="mt-3 pt-2 border-top">
                <!-- Процент заполненности -->
                <div v-if="month.completion_percentage !== null" class="mb-2">
                  <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="small text-muted">Заполнено</span>
                    <span class="small fw-semibold" :class="getCompletionClass(month.completion_percentage)">
                      {{ month.completion_percentage }}%
                    </span>
                  </div>
                  <div class="progress" style="height: 5px;">
                    <div
                      class="progress-bar"
                      :class="getCompletionBarClass(month.completion_percentage)"
                      :style="{ width: month.completion_percentage + '%' }"
                      role="progressbar"
                      :aria-valuenow="month.completion_percentage"
                      aria-valuemin="0"
                      aria-valuemax="100"
                    ></div>
                  </div>
                </div>

                <!-- Метрики автозаполнения (только с правами) -->
                <div v-if="permissions.view_monthly_report_metrics && month.auto_fill_potential_percentage !== undefined" class="mb-2">
                  <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="small text-muted" title="Процент записей которые могут быть заполнены автоматически из inventory">
                      <i class="bi bi-robot"></i> Потенциал
                    </span>
                    <span class="small fw-semibold text-info">
                      {{ month.auto_fill_potential_percentage }}%
                    </span>
                  </div>
                  <div class="d-flex justify-content-between align-items-center">
                    <span class="small text-muted" title="Процент записей которые были заполнены автоматически и не изменены вручную">
                      <i class="bi bi-check-circle"></i> Фактически
                    </span>
                    <span class="small fw-semibold text-success">
                      {{ month.auto_fill_actual_percentage }}%
                    </span>
                  </div>
                </div>

                <!-- Количество пользователей (кликабельно) -->
                <div
                  v-if="month.unique_users_count > 0"
                  class="d-flex align-items-center small users-count-link"
                  :class="{ 'clickable': permissions.view_monthly_report_metrics }"
                  @click.prevent.stop="permissions.view_monthly_report_metrics && showUsersModal(month)"
                  :title="permissions.view_monthly_report_metrics ? 'Показать список пользователей' : ''"
                >
                  <i class="bi bi-people me-1"></i>
                  <span>{{ month.unique_users_count }} {{ getUsersLabel(month.unique_users_count) }}</span>
                  <i v-if="permissions.view_monthly_report_metrics" class="bi bi-box-arrow-up-right ms-1" style="font-size: 0.7rem;"></i>
                </div>
              </div>

              <div class="mt-2 small text-muted">
                <i class="bi bi-chevron-right"></i> открыть отчёт
              </div>
            </div>

            <!-- Маленькие кнопки внизу справа -->
            <div class="card-buttons">
              <!-- Кнопка публикации (только для админов) -->
              <button
                v-if="permissions.manage_months"
                class="btn btn-sm publish-toggle-btn"
                :class="month.is_published ? 'btn-outline-warning' : 'btn-outline-success'"
                :title="month.is_published ? 'Скрыть месяц от пользователей' : 'Опубликовать месяц для всех'"
                @click.prevent.stop="togglePublished(month)"
              >
                <i :class="month.is_published ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
              </button>

              <!-- Кнопка экспорта -->
              <a
                :href="`/monthly-report/${month.year}/${month.month_number}/export-excel/`"
                class="btn btn-sm btn-outline-secondary export-btn"
                title="Скачать Excel"
                @click.stop
              >
                <i class="bi bi-download"></i>
              </a>
            </div>
          </div>
        </a>
      </div>

      <div v-if="filteredMonths.length === 0" class="col">
        <div class="alert alert-secondary mb-0">
          {{ months.length === 0 ? 'Нет загруженных месяцев.' : 'Нет результатов по вашему запросу.' }}
        </div>
      </div>
    </div>

    <!-- Модальное окно с пользователями -->
    <div v-if="showUsersDialog" class="modal fade show d-block" tabindex="-1" role="dialog" style="background-color: rgba(0,0,0,0.5);">
      <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-people"></i>
              Пользователи редактировавшие {{ selectedMonth?.month_name }} {{ selectedMonth?.year }}
            </h5>
            <button type="button" class="btn-close" @click="closeUsersModal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <!-- Загрузка -->
            <div v-if="usersLoading" class="text-center py-3">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
              </div>
            </div>

            <!-- Ошибка -->
            <div v-else-if="usersError" class="alert alert-danger">
              <i class="bi bi-exclamation-triangle"></i>
              {{ usersError }}
            </div>

            <!-- Таблица пользователей -->
            <div v-else-if="usersData" class="table-responsive">
              <table class="table table-hover table-sm">
                <thead>
                  <tr>
                    <th style="width: 40px;">№</th>
                    <th>ФИО</th>
                    <th style="width: 110px;">Логин</th>
                    <th class="text-end" style="width: 140px;" title="Редактирование полей которые были заполнены автоматически">
                      <i class="bi bi-pencil-square text-warning"></i> Отред. авто
                    </th>
                    <th class="text-end" style="width: 110px;" title="Заполнение полей которые были пустыми">
                      <i class="bi bi-plus-circle text-info"></i> Заполнил
                    </th>
                    <th class="text-end" style="width: 90px;">Всего</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(user, index) in usersData.users" :key="user.username">
                    <td>{{ index + 1 }}</td>
                    <td>{{ user.full_name }}</td>
                    <td><code class="small">{{ user.username }}</code></td>
                    <td class="text-end">
                      <span class="badge bg-warning-subtle text-warning-emphasis">
                        {{ user.edited_auto_count }}
                      </span>
                    </td>
                    <td class="text-end">
                      <span class="badge bg-info-subtle text-info-emphasis">
                        {{ user.filled_empty_count }}
                      </span>
                    </td>
                    <td class="text-end">
                      <span class="badge bg-primary-subtle text-primary-emphasis">
                        {{ user.changes_count }}
                      </span>
                    </td>
                  </tr>
                </tbody>
                <tfoot v-if="usersData.users.length > 1">
                  <tr class="fw-semibold">
                    <td colspan="3">Итого</td>
                    <td class="text-end">
                      <span class="badge bg-warning-subtle text-warning-emphasis">
                        {{ usersData.total_edited_auto }}
                      </span>
                    </td>
                    <td class="text-end">
                      <span class="badge bg-info-subtle text-info-emphasis">
                        {{ usersData.total_filled_empty }}
                      </span>
                    </td>
                    <td class="text-end">
                      <span class="badge bg-success-subtle text-success-emphasis">
                        {{ usersData.total_changes }}
                      </span>
                    </td>
                  </tr>
                </tfoot>
              </table>

              <div v-if="usersData.users.length === 0" class="alert alert-secondary mb-0">
                Нет данных об изменениях
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="closeUsersModal">Закрыть</button>
          </div>
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

// Users modal
const showUsersDialog = ref(false)
const selectedMonth = ref(null)
const usersData = ref(null)
const usersLoading = ref(false)
const usersError = ref(null)

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

// Определяет класс цвета для текста процента заполненности
function getCompletionClass(percentage) {
  if (percentage >= 90) return 'text-success'
  if (percentage >= 70) return 'text-warning'
  return 'text-danger'
}

// Определяет класс цвета для прогресс-бара
function getCompletionBarClass(percentage) {
  if (percentage >= 90) return 'bg-success'
  if (percentage >= 70) return 'bg-warning'
  return 'bg-danger'
}

// Склонение слова "пользователь"
function getUsersLabel(count) {
  const lastDigit = count % 10
  const lastTwoDigits = count % 100

  if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
    return 'пользователей'
  }

  if (lastDigit === 1) {
    return 'пользователь'
  }

  if (lastDigit >= 2 && lastDigit <= 4) {
    return 'пользователя'
  }

  return 'пользователей'
}

// Get CSRF token from cookie
function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return ''
}

// Показать модальное окно с пользователями
async function showUsersModal(month) {
  selectedMonth.value = month
  showUsersDialog.value = true
  usersLoading.value = true
  usersError.value = null
  usersData.value = null

  try {
    const response = await fetch(
      `/monthly-report/api/month-users-stats/${month.year}/${month.month_number}/`
    )
    const data = await response.json()

    if (data.ok) {
      usersData.value = data
    } else {
      usersError.value = data.error || 'Не удалось загрузить данные пользователей'
    }
  } catch (error) {
    console.error('Error loading users stats:', error)
    usersError.value = 'Ошибка загрузки данных пользователей'
  } finally {
    usersLoading.value = false
  }
}

// Закрыть модальное окно
function closeUsersModal() {
  showUsersDialog.value = false
  selectedMonth.value = null
  usersData.value = null
  usersError.value = null
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

.month-card {
  transition: transform 0.12s ease, box-shadow 0.12s ease;
  border-radius: 1rem;
  position: relative;
}

.month-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 0.25rem 1rem rgba(0, 0, 0, 0.08);
}

.month-card .bi {
  opacity: 0.7;
}

.month-badge {
  font-weight: 600;
}

/* Название месяца черное */
.month-card .fw-semibold {
  color: #212529;
}

/* Контейнер для маленьких кнопок внизу справа */
.card-buttons {
  position: absolute;
  bottom: 0.75rem;
  right: 0.75rem;
  z-index: 10;
  display: flex;
  gap: 0.25rem;
}

.card-buttons .btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  background-color: white;
  transition: all 0.15s ease;
}

.card-buttons .btn:hover {
  transform: scale(1.1);
}

/* Кнопка публикации */
.publish-toggle-btn.btn-outline-success {
  border-color: #198754;
  color: #198754;
}

.publish-toggle-btn.btn-outline-success:hover {
  background-color: #198754;
  border-color: #198754;
  color: white;
}

.publish-toggle-btn.btn-outline-warning {
  border-color: #ffc107;
  color: #ffc107;
}

.publish-toggle-btn.btn-outline-warning:hover {
  background-color: #ffc107;
  border-color: #ffc107;
  color: #000;
}

/* Кнопка экспорта */
.export-btn {
  border-color: #6c757d;
  color: #6c757d;
}

.export-btn:hover {
  background-color: #6c757d;
  border-color: #6c757d;
  color: white;
}

/* Кликабельный элемент для количества пользователей */
.users-count-link.clickable {
  cursor: pointer;
  color: #0d6efd;
  transition: color 0.15s ease;
}

.users-count-link.clickable:hover {
  color: #0a58ca;
  text-decoration: underline;
}

.users-count-link:not(.clickable) {
  color: #6c757d;
}
</style>
