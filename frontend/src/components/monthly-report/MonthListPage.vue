<template>
  <div class="month-list-page">
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

              <div class="mt-3 small text-muted">
                <i class="bi bi-chevron-right"></i> открыть отчёт
              </div>
            </div>

            <!-- Export button -->
            <a
              :href="`/monthly-report/${month.year}/${month.month_number}/export-excel/`"
              class="btn export-btn"
              title="Скачать Excel"
              @click.stop
            >
              <i class="bi bi-download"></i>
            </a>
          </div>
        </a>
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
import { ref, computed, onMounted } from 'vue'

const months = ref([])
const loading = ref(true)
const searchQuery = ref('')
const selectedYear = ref('')
const permissions = ref({})

// Computed properties
const availableYears = computed(() => {
  const years = [...new Set(months.value.map(m => m.year))]
  return years.sort((a, b) => b - a)
})

const filteredMonths = computed(() => {
  let result = months.value

  // Filter by year
  if (selectedYear.value) {
    result = result.filter(m => m.year === selectedYear.value)
  }

  // Filter by search query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.trim().toLowerCase()
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

onMounted(() => {
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

/* Кнопка экспорта внизу справа - прозрачная с зеленой иконкой */
.export-btn {
  position: absolute;
  bottom: 0.75rem;
  right: 0.75rem;
  z-index: 10;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  background-color: transparent !important;
  border: none;
  color: #198754;
}

.export-btn:hover {
  transform: scale(1.1);
  color: #157347;
}

.export-btn .bi {
  opacity: 1;
}
</style>
