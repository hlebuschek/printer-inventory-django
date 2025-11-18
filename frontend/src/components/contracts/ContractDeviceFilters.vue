<template>
  <div class="contract-filters card mb-4">
    <div class="card-body">
      <div class="row g-3">
        <!-- Организация -->
        <div class="col-md-3">
          <label class="form-label">Организация</label>
          <select v-model="localFilters.organization" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="org in filterData.organizations" :key="org.id" :value="org.name">
              {{ org.name }}
            </option>
          </select>
        </div>

        <!-- Город -->
        <div class="col-md-3">
          <label class="form-label">Город</label>
          <select v-model="localFilters.city" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="city in filterData.cities" :key="city.id" :value="city.name">
              {{ city.name }}
            </option>
          </select>
        </div>

        <!-- Адрес -->
        <div class="col-md-3">
          <label class="form-label">Адрес</label>
          <input
            v-model="localFilters.address"
            type="text"
            class="form-control form-control-sm"
            placeholder="Поиск по адресу"
          />
        </div>

        <!-- Кабинет -->
        <div class="col-md-3">
          <label class="form-label">Кабинет</label>
          <input
            v-model="localFilters.room"
            type="text"
            class="form-control form-control-sm"
            placeholder="№ кабинета"
          />
        </div>

        <!-- Производитель -->
        <div class="col-md-3">
          <label class="form-label">Производитель</label>
          <select v-model="localFilters.manufacturer" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="mfr in filterData.manufacturers" :key="mfr.id" :value="mfr.name">
              {{ mfr.name }}
            </option>
          </select>
        </div>

        <!-- Модель -->
        <div class="col-md-3">
          <label class="form-label">Модель</label>
          <input
            v-model="localFilters.model"
            type="text"
            class="form-control form-control-sm"
            placeholder="Поиск по модели"
          />
        </div>

        <!-- Серийный номер -->
        <div class="col-md-3">
          <label class="form-label">Серийный номер</label>
          <input
            v-model="localFilters.serial"
            type="text"
            class="form-control form-control-sm"
            placeholder="Поиск по S/N"
          />
        </div>

        <!-- Статус -->
        <div class="col-md-3">
          <label class="form-label">Статус</label>
          <select v-model="localFilters.status" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="status in filterData.statuses" :key="status.id" :value="status.name">
              {{ status.name }}
            </option>
          </select>
        </div>

        <!-- Месяц обслуживания -->
        <div class="col-md-3">
          <label class="form-label">Месяц обслуживания</label>
          <input
            v-model="localFilters.service_month"
            type="text"
            class="form-control form-control-sm"
            placeholder="MM.YYYY"
          />
        </div>

        <!-- Комментарий -->
        <div class="col-md-9">
          <label class="form-label">Комментарий</label>
          <input
            v-model="localFilters.comment"
            type="text"
            class="form-control form-control-sm"
            placeholder="Поиск в комментариях"
          />
        </div>
      </div>

      <!-- Кнопки -->
      <div class="row mt-3">
        <div class="col">
          <button class="btn btn-primary btn-sm me-2" @click="handleApply">
            <i class="bi bi-funnel me-1"></i>
            Применить фильтры
          </button>
          <button class="btn btn-secondary btn-sm me-2" @click="handleReset">
            <i class="bi bi-x-circle me-1"></i>
            Сбросить
          </button>
          <button class="btn btn-success btn-sm" @click="handleExport">
            <i class="bi bi-file-earmark-excel me-1"></i>
            Экспорт в Excel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  },
  filterData: {
    type: Object,
    default: () => ({
      organizations: [],
      cities: [],
      manufacturers: [],
      statuses: []
    })
  }
})

const emit = defineEmits(['update:filters', 'apply', 'reset', 'export-excel'])

// Локальная копия фильтров для двусторонней привязки
const localFilters = reactive({ ...props.filters })

// Синхронизация изменений с родителем
watch(
  localFilters,
  (newValue) => {
    emit('update:filters', newValue)
  },
  { deep: true }
)

function handleApply() {
  emit('apply')
}

function handleReset() {
  emit('reset')
}

function handleExport() {
  emit('export-excel')
}
</script>

<style scoped>
.contract-filters {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
}

.form-label {
  font-weight: 500;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
  color: #495057;
}
</style>
