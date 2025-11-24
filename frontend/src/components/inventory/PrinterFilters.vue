<template>
  <form class="row g-2 mb-3" @submit.prevent="$emit('apply')">
    <!-- IP Address -->
    <div class="col-auto">
      <input
        v-model="localFilters.q_ip"
        type="text"
        class="form-control"
        placeholder="IP-адрес"
      />
    </div>

    <!-- Serial Number -->
    <div class="col-auto">
      <input
        v-model="localFilters.q_serial"
        type="text"
        class="form-control"
        placeholder="Серийный №"
      />
    </div>

    <!-- Manufacturer -->
    <div class="col-auto">
      <select
        v-model="localFilters.q_manufacturer"
        class="form-select"
        @change="onManufacturerChange"
      >
        <option value="">Производитель (все)</option>
        <option
          v-for="mfr in manufacturers"
          :key="mfr.id"
          :value="mfr.id"
        >
          {{ mfr.name }}
        </option>
      </select>
    </div>

    <!-- Device Model -->
    <div class="col-auto">
      <select
        v-model="localFilters.q_device_model"
        class="form-select"
        :disabled="!localFilters.q_manufacturer && !filteredModels.length"
      >
        <option value="">Модель (все)</option>
        <option
          v-for="model in filteredModels"
          :key="model.id"
          :value="model.id"
        >
          {{ model.name }}
        </option>
      </select>
    </div>

    <!-- Model Text Search -->
    <div class="col-auto">
      <input
        v-model="localFilters.q_model_text"
        type="text"
        class="form-control"
        placeholder="Поиск по модели"
        title="Текстовый поиск по названию модели или производителя"
        @input="onModelTextInput"
      />
    </div>

    <!-- Organization -->
    <div class="col-auto">
      <select
        v-model="localFilters.q_org"
        class="form-select"
      >
        <option value="">Организация (все)</option>
        <option value="none">— без организации —</option>
        <option
          v-for="org in organizations"
          :key="org.id"
          :value="org.id"
        >
          {{ org.name }}
        </option>
      </select>
    </div>

    <!-- Match Rule -->
    <div class="col-auto">
      <select
        v-model="localFilters.q_rule"
        class="form-select"
      >
        <option value="">Правило (все)</option>
        <option value="SN_MAC">Серийник+MAC</option>
        <option value="MAC_ONLY">Только MAC</option>
        <option value="SN_ONLY">Только серийник</option>
        <option value="NONE">Нет данных</option>
      </select>
    </div>

    <!-- Action Buttons -->
    <div class="col-auto d-flex align-items-end">
      <button type="submit" class="btn btn-primary me-2">
        <i class="bi bi-funnel me-1"></i> Фильтровать
      </button>

      <button type="button" class="btn btn-primary me-2" @click="$emit('reset')">
        <i class="bi bi-x-circle me-1"></i> Сброс
      </button>

      <button
        v-if="permissions.export_printers"
        type="button"
        class="btn btn-primary me-2"
        @click="$emit('export-excel')"
      >
        <i class="bi bi-file-earmark-excel me-1"></i> Экспорт в Excel
      </button>

      <button
        v-if="permissions.export_amb_report"
        type="button"
        class="btn btn-primary me-2"
        @click="$emit('export-amb')"
      >
        <i class="bi bi-file-earmark-text me-1"></i> Отчет для АМБ
      </button>

      <button
        type="button"
        class="btn btn-primary"
        @click="$emit('open-column-selector')"
      >
        <i class="bi bi-table me-1"></i> Выбрать столбцы
      </button>
    </div>
  </form>
</template>

<script setup>
import { computed, watch } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  },
  manufacturers: {
    type: Array,
    default: () => []
  },
  deviceModels: {
    type: Array,
    default: () => []
  },
  organizations: {
    type: Array,
    default: () => []
  },
  permissions: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:filters', 'apply', 'reset', 'export-excel', 'export-amb', 'open-column-selector'])

const localFilters = computed({
  get: () => props.filters,
  set: (value) => emit('update:filters', value)
})

const filteredModels = computed(() => {
  if (!localFilters.value.q_manufacturer) {
    return props.deviceModels
  }

  return props.deviceModels.filter(
    model => String(model.manufacturer_id) === String(localFilters.value.q_manufacturer)
  )
})

function onManufacturerChange() {
  // Clear device model when manufacturer changes
  if (!localFilters.value.q_manufacturer) {
    localFilters.value.q_device_model = ''
  }
  // Clear text search when dropdown is selected
  if (localFilters.value.q_manufacturer) {
    localFilters.value.q_model_text = ''
  }
}

function onModelTextInput() {
  // Clear dropdowns when text is entered
  if (localFilters.value.q_model_text) {
    localFilters.value.q_manufacturer = ''
    localFilters.value.q_device_model = ''
  }
}

// Watch for manufacturer changes to update models list
watch(
  () => localFilters.value.q_manufacturer,
  (newManufacturerId, oldManufacturerId) => {
    if (newManufacturerId !== oldManufacturerId && !newManufacturerId) {
      localFilters.value.q_device_model = ''
    }
  }
)
</script>
