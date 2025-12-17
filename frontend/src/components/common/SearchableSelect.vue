<template>
  <div class="searchable-select" ref="containerRef">
    <div class="input-wrapper">
      <input
        ref="inputRef"
        v-model="searchQuery"
        type="text"
        class="form-control"
        :placeholder="placeholder"
        :disabled="disabled"
        @focus="showDropdown = true"
        @input="onInput"
        @keydown.down.prevent="navigateDown"
        @keydown.up.prevent="navigateUp"
        @keydown.enter.prevent="selectHighlighted"
        @keydown.escape="closeDropdown"
      />
      <button
        v-if="modelValue"
        type="button"
        class="btn-clear"
        :title="'Очистить'"
        @click="clear"
      >
        ×
      </button>
    </div>

    <!-- Dropdown list -->
    <div v-if="showDropdown && filteredOptions.length > 0" class="dropdown-list">
      <div
        v-for="(option, index) in filteredOptions"
        :key="option.value"
        :class="['dropdown-item', { 'highlighted': index === highlightedIndex, 'selected': option.value === modelValue }]"
        @mousedown.prevent="selectOption(option)"
        @mouseenter="highlightedIndex = index"
      >
        {{ option.label }}
      </div>
    </div>

    <!-- No results -->
    <div v-if="showDropdown && searchQuery && filteredOptions.length === 0" class="dropdown-list">
      <div class="dropdown-item disabled">
        Ничего не найдено
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  options: {
    type: Array,
    required: true,
    // Expected format: [{ value: '1', label: 'Option 1' }, ...]
  },
  placeholder: {
    type: String,
    default: 'Выберите...'
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const containerRef = ref(null)
const inputRef = ref(null)
const searchQuery = ref('')
const showDropdown = ref(false)
const highlightedIndex = ref(0)

// Filtered options based on search query
const filteredOptions = computed(() => {
  if (!searchQuery.value) {
    return props.options
  }

  const query = searchQuery.value.toLowerCase()
  return props.options.filter(option =>
    option.label.toLowerCase().includes(query)
  )
})

// Find selected option label
const selectedOption = computed(() => {
  return props.options.find(opt => opt.value === props.modelValue)
})

// Update search query when model value changes
watch(() => props.modelValue, (newValue) => {
  if (newValue) {
    const option = props.options.find(opt => opt.value === newValue)
    if (option) {
      searchQuery.value = option.label
    }
  } else {
    searchQuery.value = ''
  }
}, { immediate: true })

function onInput() {
  showDropdown.value = true
  highlightedIndex.value = 0

  // If query is empty, clear selection
  if (!searchQuery.value) {
    emit('update:modelValue', '')
  }
}

function selectOption(option) {
  emit('update:modelValue', option.value)
  searchQuery.value = option.label
  showDropdown.value = false
}

function selectHighlighted() {
  if (filteredOptions.value.length > 0 && highlightedIndex.value >= 0) {
    selectOption(filteredOptions.value[highlightedIndex.value])
  }
}

function navigateDown() {
  if (highlightedIndex.value < filteredOptions.value.length - 1) {
    highlightedIndex.value++
  }
}

function navigateUp() {
  if (highlightedIndex.value > 0) {
    highlightedIndex.value--
  }
}

function closeDropdown() {
  showDropdown.value = false

  // Restore selected option label if exists
  if (props.modelValue && selectedOption.value) {
    searchQuery.value = selectedOption.value.label
  } else if (!searchQuery.value) {
    searchQuery.value = ''
  }
}

function clear() {
  emit('update:modelValue', '')
  searchQuery.value = ''
  showDropdown.value = false
  inputRef.value?.focus()
}

// Click outside handler
function handleClickOutside(event) {
  if (containerRef.value && !containerRef.value.contains(event.target)) {
    closeDropdown()
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
.searchable-select {
  position: relative;
  width: 100%;
}

.input-wrapper {
  position: relative;
}

.btn-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  color: #6c757d;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-clear:hover {
  color: #dc3545;
}

.dropdown-list {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 0.375rem;
  margin-top: 2px;
  max-height: 300px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.dropdown-item {
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: background-color 0.15s;
}

.dropdown-item:hover,
.dropdown-item.highlighted {
  background-color: #f8f9fa;
}

.dropdown-item.selected {
  background-color: #e7f1ff;
  font-weight: 500;
}

.dropdown-item.disabled {
  color: #6c757d;
  cursor: default;
}

.dropdown-item.disabled:hover {
  background-color: transparent;
}

/* Scrollbar styling */
.dropdown-list::-webkit-scrollbar {
  width: 8px;
}

.dropdown-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 0 0.375rem 0.375rem 0;
}

.dropdown-list::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.dropdown-list::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
