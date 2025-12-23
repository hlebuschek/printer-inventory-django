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

      <button
        v-if="permissions.sync_from_inventory"
        class="btn btn-primary btn-sm ms-2"
        @click="startGlpiExport"
        :disabled="glpiExportInProgress"
      >
        <i class="bi bi-cloud-upload"></i> Выгрузка в GLPI
      </button>
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

              <!-- Кнопка удаления (только для пользователей с правом can_delete_month) -->
              <button
                v-if="permissions.can_delete_month"
                class="btn btn-sm btn-outline-danger delete-btn"
                title="Удалить месяц и все данные"
                @click.prevent.stop="deleteMonth(month)"
              >
                <i class="bi bi-trash"></i>
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
                    <th style="width: 50px;">№</th>
                    <th class="sortable-header" @click="changeSorting('full_name')" style="cursor: pointer; white-space: nowrap;">
                      <span>ФИО</span>
                      <i class="bi" :class="getSortIcon('full_name')"></i>
                    </th>
                    <th style="width: 120px;">Логин</th>
                    <th class="text-end sortable-header" style="width: 160px; cursor: pointer; white-space: nowrap;"
                        title="Редактирование полей которые были заполнены автоматически"
                        @click="changeSorting('edited_auto_count')">
                      <span><i class="bi bi-pencil-square text-warning"></i> Отред. авто</span>
                      <i class="bi" :class="getSortIcon('edited_auto_count')"></i>
                    </th>
                    <th class="text-end sortable-header" style="width: 130px; cursor: pointer; white-space: nowrap;"
                        title="Заполнение полей которые были пустыми"
                        @click="changeSorting('filled_empty_count')">
                      <span><i class="bi bi-plus-circle text-info"></i> Заполнил</span>
                      <i class="bi" :class="getSortIcon('filled_empty_count')"></i>
                    </th>
                    <th class="text-end sortable-header" style="width: 110px; cursor: pointer; white-space: nowrap;"
                        @click="changeSorting('changes_count')">
                      <span>Всего</span>
                      <i class="bi" :class="getSortIcon('changes_count')"></i>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(user, index) in sortedUsers" :key="user.username">
                    <td>{{ index + 1 }}</td>
                    <td>{{ user.full_name }}</td>
                    <td><code class="small">{{ user.username }}</code></td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(user.full_name, 'edited_auto')"
                        class="badge bg-warning-subtle text-warning-emphasis text-decoration-none change-badge"
                        :title="`Показать изменения автоматических счетчиков пользователя ${user.full_name}`"
                        @click.stop
                      >
                        {{ user.edited_auto_count }}
                      </a>
                    </td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(user.full_name, 'filled_empty')"
                        class="badge bg-info-subtle text-info-emphasis text-decoration-none change-badge"
                        :title="`Показать заполненные пустые поля пользователем ${user.full_name}`"
                        @click.stop
                      >
                        {{ user.filled_empty_count }}
                      </a>
                    </td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(user.full_name, 'all')"
                        class="badge bg-primary-subtle text-primary-emphasis text-decoration-none change-badge"
                        :title="`Показать все изменения пользователя ${user.full_name}`"
                        @click.stop
                      >
                        {{ user.changes_count }}
                      </a>
                    </td>
                  </tr>
                </tbody>
                <tfoot v-if="usersData.users.length > 1">
                  <tr class="fw-semibold">
                    <td colspan="3">Итого</td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(null, 'edited_auto')"
                        class="badge bg-warning-subtle text-warning-emphasis text-decoration-none change-badge"
                        title="Показать все изменения автоматических счетчиков"
                        @click.stop
                      >
                        {{ usersData.total_edited_auto }}
                      </a>
                    </td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(null, 'filled_empty')"
                        class="badge bg-info-subtle text-info-emphasis text-decoration-none change-badge"
                        title="Показать все заполненные пустые поля"
                        @click.stop
                      >
                        {{ usersData.total_filled_empty }}
                      </a>
                    </td>
                    <td class="text-end">
                      <a
                        :href="getUserChangesLink(null, 'all')"
                        class="badge bg-success-subtle text-success-emphasis text-decoration-none change-badge"
                        title="Показать все изменения"
                        @click.stop
                      >
                        {{ usersData.total_changes }}
                      </a>
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

    <!-- Модальное окно выгрузки в GLPI -->
    <div v-if="showGlpiExportDialog" class="modal fade show d-block" tabindex="-1" role="dialog" style="background-color: rgba(0,0,0,0.5);">
      <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-cloud-upload"></i>
              Выгрузка счетчиков в GLPI
            </h5>
            <button
              type="button"
              class="btn-close"
              @click="closeGlpiExportDialog"
              :disabled="glpiExportInProgress"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <!-- Статус выгрузки -->
            <div v-if="glpiExportState === 'starting'" class="text-center py-3">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Запуск...</span>
              </div>
              <p class="mt-2 text-muted">Запуск задачи выгрузки...</p>
            </div>

            <!-- Прогресс выгрузки -->
            <div v-else-if="glpiExportState === 'progress' || glpiExportState === 'pending'">
              <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="fw-semibold">{{ glpiExportProgress.message || 'Выполнение...' }}</span>
                  <span class="badge bg-primary">{{ glpiExportProgress.percent }}%</span>
                </div>
                <div class="progress" style="height: 25px;">
                  <div
                    class="progress-bar progress-bar-striped progress-bar-animated"
                    role="progressbar"
                    :style="{ width: glpiExportProgress.percent + '%' }"
                    :aria-valuenow="glpiExportProgress.percent"
                    aria-valuemin="0"
                    aria-valuemax="100"
                  >
                    {{ glpiExportProgress.current }} / {{ glpiExportProgress.total }}
                  </div>
                </div>
              </div>
              <p class="small text-muted mb-0">
                <i class="bi bi-info-circle"></i>
                Не закрывайте это окно до завершения выгрузки
              </p>
            </div>

            <!-- Результат выгрузки -->
            <div v-else-if="glpiExportState === 'success'">
              <div class="alert alert-success">
                <i class="bi bi-check-circle"></i>
                {{ glpiExportResult.message || 'Выгрузка завершена' }}
              </div>

              <div class="row text-center mb-3">
                <div class="col-4">
                  <div class="card border-success">
                    <div class="card-body py-2">
                      <h4 class="mb-0 text-success">{{ glpiExportResult.exported || 0 }}</h4>
                      <small class="text-muted">Выгружено</small>
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="card border-secondary">
                    <div class="card-body py-2">
                      <h4 class="mb-0">{{ glpiExportResult.total || 0 }}</h4>
                      <small class="text-muted">Всего</small>
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="card" :class="glpiExportResult.errors > 0 ? 'border-danger' : 'border-secondary'">
                    <div class="card-body py-2">
                      <h4 class="mb-0" :class="glpiExportResult.errors > 0 ? 'text-danger' : ''">
                        {{ glpiExportResult.errors || 0 }}
                      </h4>
                      <small class="text-muted">Ошибок</small>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Таблица ошибок -->
              <div v-if="glpiExportResult.errors > 0 && glpiExportResult.error_details && glpiExportResult.error_details.length > 0" class="mt-3">
                <h6 class="text-danger">
                  <i class="bi bi-exclamation-triangle"></i>
                  Ошибки выгрузки ({{ glpiExportResult.error_details.length }})
                </h6>
                <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
                  <table class="table table-sm table-hover">
                    <thead class="table-light sticky-top">
                      <tr>
                        <th style="width: 50px;">№</th>
                        <th>Серийный номер</th>
                        <th>Инв. номер</th>
                        <th>GLPI ID</th>
                        <th>Ошибка</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(error, index) in glpiExportResult.error_details" :key="index">
                        <td>{{ index + 1 }}</td>
                        <td><code class="small">{{ error.serial_number || '-' }}</code></td>
                        <td>{{ error.inventory_number || '-' }}</td>
                        <td>{{ error.glpi_id || '-' }}</td>
                        <td class="small text-danger">{{ error.error }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- Ошибка выгрузки -->
            <div v-else-if="glpiExportState === 'error'">
              <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                {{ glpiExportError || 'Произошла ошибка при выгрузке' }}
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              @click="closeGlpiExportDialog"
              :disabled="glpiExportInProgress"
            >
              {{ glpiExportInProgress ? 'Подождите...' : 'Закрыть' }}
            </button>
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

// Sorting for users table
const sortField = ref('changes_count') // По умолчанию сортировка по количеству изменений
const sortDirection = ref('desc') // desc или asc

// GLPI Export
const showGlpiExportDialog = ref(false)
const glpiExportState = ref(null) // 'starting', 'pending', 'progress', 'success', 'error'
const glpiExportInProgress = ref(false)
const glpiExportTaskId = ref(null)
const glpiExportProgress = ref({ current: 0, total: 0, percent: 0, message: '' })
const glpiExportResult = ref({})
const glpiExportError = ref(null)
let glpiExportPollingInterval = null

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

// Sorted users list
const sortedUsers = computed(() => {
  if (!usersData.value || !usersData.value.users) {
    return []
  }

  const users = [...usersData.value.users]

  users.sort((a, b) => {
    let aVal = a[sortField.value]
    let bVal = b[sortField.value]

    // Для строковых полей (ФИО) делаем case-insensitive сортировку
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }

    let comparison = 0
    if (aVal > bVal) {
      comparison = 1
    } else if (aVal < bVal) {
      comparison = -1
    }

    return sortDirection.value === 'asc' ? comparison : -comparison
  })

  return users
})

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

// Delete month and all related data
async function deleteMonth(month) {
  const confirmMessage = `⚠️ ВНИМАНИЕ! Это действие необратимо!\n\n` +
    `Будут удалены:\n` +
    `• Все записи месяца (${month.count} шт.)\n` +
    `• История изменений\n` +
    `• Настройки месяца\n\n` +
    `Вы уверены, что хотите удалить ${month.month_name} ${month.year}?`

  if (!confirm(confirmMessage)) {
    return
  }

  // Двойное подтверждение для критичной операции
  const doubleConfirm = prompt(
    `Для подтверждения удаления введите название месяца и год: "${month.month_name} ${month.year}"`
  )

  if (doubleConfirm !== `${month.month_name} ${month.year}`) {
    showToast(
      'Отменено',
      'Удаление отменено. Введённый текст не совпадает.',
      'warning'
    )
    return
  }

  try {
    const response = await fetch('/monthly-report/api/delete-month/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        year: month.year,
        month: month.month_number
      })
    })

    const data = await response.json()

    if (data.success) {
      // Удаляем месяц из списка
      const index = months.value.findIndex(
        m => m.year === month.year && m.month_number === month.month_number
      )
      if (index !== -1) {
        months.value.splice(index, 1)
      }

      showToast(
        'Успешно',
        `${data.message}\nУдалено записей: ${data.deleted_records}`,
        'success'
      )
    } else {
      showToast(
        'Ошибка',
        data.error || 'Не удалось удалить месяц',
        'error'
      )
    }
  } catch (error) {
    console.error('Error deleting month:', error)
    showToast(
      'Ошибка',
      'Не удалось удалить месяц',
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
  // Сброс сортировки
  sortField.value = 'changes_count'
  sortDirection.value = 'desc'
}

// Изменить сортировку
function changeSorting(field) {
  if (sortField.value === field) {
    // Если кликнули по той же колонке, меняем направление
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    // Если новая колонка, устанавливаем desc по умолчанию для числовых, asc для ФИО
    sortField.value = field
    sortDirection.value = field === 'full_name' ? 'asc' : 'desc'
  }
}

// Получить иконку для заголовка таблицы
function getSortIcon(field) {
  if (sortField.value !== field) {
    return 'bi-arrow-down-up' // Нейтральная иконка
  }
  return sortDirection.value === 'asc' ? 'bi-arrow-up' : 'bi-arrow-down'
}

// Получить ссылку для перехода к изменениям пользователя
function getUserChangesLink(fullName, changeType) {
  if (!selectedMonth.value) return '#'

  const baseUrl = `/monthly-report/month-changes/${selectedMonth.value.year}/${selectedMonth.value.month_number}/`
  const params = new URLSearchParams()

  if (fullName) {
    params.append('filter_user', fullName)
  }

  if (changeType !== 'all') {
    params.append('filter_change_type', changeType)
  }

  return `${baseUrl}?${params.toString()}`
}

// GLPI Export Functions
async function startGlpiExport() {
  showGlpiExportDialog.value = true
  glpiExportState.value = 'starting'
  glpiExportInProgress.value = true
  glpiExportError.value = null
  glpiExportResult.value = {}

  try {
    const response = await fetch('/monthly-report/api/glpi-export/start/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      }
    })

    const data = await response.json()

    if (data.ok) {
      glpiExportTaskId.value = data.task_id
      glpiExportState.value = 'pending'

      // Начинаем опрашивать статус задачи
      pollGlpiExportStatus()
    } else {
      glpiExportState.value = 'error'
      glpiExportError.value = data.error || 'Не удалось запустить выгрузку'
      glpiExportInProgress.value = false
    }
  } catch (error) {
    console.error('Error starting GLPI export:', error)
    glpiExportState.value = 'error'
    glpiExportError.value = 'Ошибка запуска выгрузки'
    glpiExportInProgress.value = false
  }
}

async function pollGlpiExportStatus() {
  // Очищаем предыдущий интервал если был
  if (glpiExportPollingInterval) {
    clearInterval(glpiExportPollingInterval)
  }

  // Запрашиваем статус каждые 2 секунды
  glpiExportPollingInterval = setInterval(async () => {
    try {
      const response = await fetch(
        `/monthly-report/api/glpi-export/status/${glpiExportTaskId.value}/`
      )
      const data = await response.json()

      if (data.state === 'PENDING') {
        glpiExportState.value = 'pending'
        glpiExportProgress.value = {
          current: data.current || 0,
          total: data.total || 1,
          percent: data.percent || 0,
          message: data.message || 'Ожидание...'
        }
      } else if (data.state === 'PROGRESS') {
        glpiExportState.value = 'progress'
        glpiExportProgress.value = {
          current: data.current || 0,
          total: data.total || 1,
          percent: data.percent || 0,
          message: data.message || 'Выполнение...'
        }
      } else if (data.state === 'SUCCESS') {
        glpiExportState.value = 'success'
        glpiExportResult.value = data.result || {}
        glpiExportInProgress.value = false
        clearInterval(glpiExportPollingInterval)
        glpiExportPollingInterval = null

        // Показываем toast уведомление
        if (glpiExportResult.value.errors === 0) {
          showToast(
            'Успешно',
            `Выгружено ${glpiExportResult.value.exported} устройств в GLPI`,
            'success'
          )
        } else {
          showToast(
            'Выполнено с ошибками',
            `Выгружено ${glpiExportResult.value.exported} из ${glpiExportResult.value.total}. Ошибок: ${glpiExportResult.value.errors}`,
            'warning'
          )
        }
      } else if (data.state === 'FAILURE') {
        glpiExportState.value = 'error'
        glpiExportError.value = data.error || 'Ошибка выполнения задачи'
        glpiExportInProgress.value = false
        clearInterval(glpiExportPollingInterval)
        glpiExportPollingInterval = null

        showToast(
          'Ошибка',
          glpiExportError.value,
          'error'
        )
      }
    } catch (error) {
      console.error('Error polling GLPI export status:', error)
      glpiExportState.value = 'error'
      glpiExportError.value = 'Ошибка получения статуса выгрузки'
      glpiExportInProgress.value = false
      clearInterval(glpiExportPollingInterval)
      glpiExportPollingInterval = null
    }
  }, 2000) // Опрашиваем каждые 2 секунды
}

function closeGlpiExportDialog() {
  if (glpiExportInProgress.value) {
    const confirmClose = confirm(
      'Выгрузка еще не завершена. Вы уверены, что хотите закрыть окно?\n\nЗадача продолжит выполняться в фоне.'
    )
    if (!confirmClose) {
      return
    }
  }

  showGlpiExportDialog.value = false

  // Очищаем интервал опроса
  if (glpiExportPollingInterval) {
    clearInterval(glpiExportPollingInterval)
    glpiExportPollingInterval = null
  }

  // Сброс состояния
  setTimeout(() => {
    glpiExportState.value = null
    glpiExportInProgress.value = false
    glpiExportTaskId.value = null
    glpiExportProgress.value = { current: 0, total: 0, percent: 0, message: '' }
    glpiExportResult.value = {}
    glpiExportError.value = null
  }, 300)
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

/* Кнопка удаления */
.delete-btn {
  border-color: #dc3545;
  color: #dc3545;
}

.delete-btn:hover {
  background-color: #dc3545;
  border-color: #dc3545;
  color: white;
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

/* Сортируемые заголовки таблицы */
.sortable-header {
  user-select: none;
  transition: background-color 0.15s ease;
}

.sortable-header:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.sortable-header span {
  display: inline-block;
}

.sortable-header i.bi {
  display: inline-block;
  font-size: 0.85rem;
  opacity: 0.6;
  margin-left: 0.35rem;
  vertical-align: middle;
}

.sortable-header:hover i.bi {
  opacity: 1;
}

/* Кликабельные бейджи с числами изменений */
.change-badge {
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-block;
}

.change-badge:hover {
  transform: scale(1.1);
  filter: brightness(0.95);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
</style>
