<template>
  <div class="multi-select" ref="containerRef">
    <div
      class="multi-select-input form-select form-select-sm"
      :class="{ 'has-selections': selectedValues.length > 0 }"
      @click="toggleDropdown"
    >
      <div v-if="selectedValues.length === 0" class="placeholder">
        {{ placeholder }}
      </div>
      <div v-else class="selected-items">
        <span
          v-for="item in selectedItems"
          :key="item[valueKey]"
          class="badge bg-primary me-1"
        >
          {{ item[labelKey] }}
          <i
            class="bi bi-x-circle ms-1"
            @click.stop="removeItem(item[valueKey])"
          ></i>
        </span>
      </div>
      <i class="bi bi-chevron-down dropdown-icon"></i>
    </div>

    <div v-if="isOpen" class="multi-select-dropdown">
      <div v-if="showSearch" class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          class="form-control form-control-sm"
          placeholder="Поиск..."
          @click.stop
        />
      </div>
      <div class="options-list">
        <div
          v-for="option in filteredOptions"
          :key="option[valueKey]"
          class="option-item"
          @click="toggleItem(option[valueKey])"
        >
          <input
            type="checkbox"
            :checked="selectedValues.includes(option[valueKey])"
            class="form-check-input"
            @click.stop
          />
          <label class="form-check-label">{{ option[labelKey] }}</label>
        </div>
        <div v-if="filteredOptions.length === 0" class="no-options">
          Нет результатов
        </div>
      </div>
      <div v-if="selectedValues.length > 0" class="dropdown-footer">
        <button
          class="btn btn-sm btn-link text-danger"
          @click.stop="clearAll"
        >
          Очистить все
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  options: {
    type: Array,
    default: () => []
  },
  labelKey: {
    type: String,
    default: 'label'
  },
  valueKey: {
    type: String,
    default: 'value'
  },
  placeholder: {
    type: String,
    default: 'Выберите...'
  },
  showSearch: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue'])

const isOpen = ref(false)
const searchQuery = ref('')
const containerRef = ref(null)

const selectedValues = computed(() => props.modelValue || [])

const selectedItems = computed(() => {
  return props.options.filter(option =>
    selectedValues.value.includes(option[props.valueKey])
  )
})

const filteredOptions = computed(() => {
  if (!searchQuery.value) return props.options

  const query = searchQuery.value.toLowerCase()
  return props.options.filter(option =>
    option[props.labelKey].toLowerCase().includes(query)
  )
})

function toggleDropdown() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchQuery.value = ''
  }
}

function toggleItem(value) {
  const newValues = [...selectedValues.value]
  const index = newValues.indexOf(value)

  if (index > -1) {
    newValues.splice(index, 1)
  } else {
    newValues.push(value)
  }

  emit('update:modelValue', newValues)
}

function removeItem(value) {
  const newValues = selectedValues.value.filter(v => v !== value)
  emit('update:modelValue', newValues)
}

function clearAll() {
  emit('update:modelValue', [])
  isOpen.value = false
}

function handleClickOutside(event) {
  if (containerRef.value && !containerRef.value.contains(event.target)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.multi-select {
  position: relative;
}

.multi-select-input {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 31px;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  user-select: none;
}

.multi-select-input.has-selections {
  padding: 0.15rem 0.5rem;
}

.placeholder {
  color: #6c757d;
  font-size: 0.875rem;
}

.selected-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  flex: 1;
}

.selected-items .badge {
  font-weight: 400;
  padding: 0.25rem 0.5rem;
  display: inline-flex;
  align-items: center;
}

.selected-items .badge i {
  cursor: pointer;
  font-size: 0.75rem;
}

.selected-items .badge i:hover {
  opacity: 0.8;
}

.dropdown-icon {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.multi-select-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  background: white;
  border: 1px solid #ced4da;
  border-radius: 0.25rem;
  margin-top: 0.25rem;
  box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
  max-height: 300px;
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 0.5rem;
  border-bottom: 1px solid #e9ecef;
}

.options-list {
  overflow-y: auto;
  max-height: 200px;
  padding: 0.25rem 0;
}

.option-item {
  padding: 0.375rem 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.option-item:hover {
  background-color: #f8f9fa;
}

.option-item .form-check-input {
  cursor: pointer;
  margin: 0;
}

.option-item .form-check-label {
  cursor: pointer;
  margin: 0;
  flex: 1;
}

.no-options {
  padding: 0.75rem;
  text-align: center;
  color: #6c757d;
  font-size: 0.875rem;
}

.dropdown-footer {
  padding: 0.5rem;
  border-top: 1px solid #e9ecef;
  text-align: right;
}

.dropdown-footer .btn {
  padding: 0.125rem 0.5rem;
  font-size: 0.875rem;
  text-decoration: none;
}

.dropdown-footer .btn:hover {
  text-decoration: underline;
}
</style>
