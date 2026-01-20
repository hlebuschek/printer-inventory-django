<template>
  <th :class="['column-filter', thClass]">
    <div class="d-flex align-items-center gap-1">
      <span class="column-label">
        {{ label }}
        <i v-if="sortState === 'asc'" class="bi bi-arrow-up text-primary ms-1"></i>
        <i v-else-if="sortState === 'desc'" class="bi bi-arrow-down text-primary ms-1"></i>
      </span>
      <div class="dropdown">
        <button
          :id="`filter-toggle-${columnKey}`"
          class="btn btn-link btn-sm p-0 text-muted"
          type="button"
          :class="{ 'filter-active': hasActiveFilter }"
          @click="toggleFilter"
        >
          <i :class="['bi', hasActiveFilter ? 'bi-funnel-fill text-primary' : 'bi-funnel']"></i>
        </button>
      </div>
    </div>

    <!-- Filter Menu Portal -->
    <teleport to="body">
      <div
        v-if="isOpen"
        ref="menuRef"
        class="filter-menu-portal p-2"
        :class="{ show: isOpen }"
        :style="menuStyle"
        @click.stop
      >
        <!-- Filter Input -->
        <div class="input-group input-group-sm mb-2">
          <input
            ref="inputRef"
            v-model="filterValue"
            type="text"
            class="form-control"
            :placeholder="placeholder"
            @keypress.enter="applyFilter"
          />
          <button class="btn btn-primary" type="button" @click.stop="applyFilter">OK</button>
        </div>

        <!-- Sort and Actions -->
        <div class="d-flex gap-1 mb-2 flex-wrap">
          <button class="btn btn-outline-secondary btn-sm" type="button" title="Сортировать по возрастанию" @click.stop="sort(false)">
            ↑
          </button>
          <button class="btn btn-outline-secondary btn-sm" type="button" title="Сортировать по убыванию" @click.stop="sort(true)">
            ↓
          </button>
          <button class="btn btn-link btn-sm text-danger ms-auto" type="button" @click.stop="clearFilter">
            Сброс
          </button>
        </div>

        <!-- Suggestions (if provided) -->
        <div v-if="suggestions && suggestions.length > 0" class="mb-2">
          <input
            v-model="searchQuery"
            type="text"
            class="form-control form-control-sm"
            placeholder="Поиск в списке..."
          />
        </div>

        <div v-if="suggestions && suggestions.length > 0" class="mb-2 small text-muted">
          Выбрано: <span class="selected-count">{{ selectedCount }}</span> из
          <span>{{ filteredSuggestions.length }}</span>
        </div>

        <div
          v-if="suggestions && suggestions.length > 0"
          class="suggestions-container"
          style="max-height: 240px; overflow-y: auto; border-radius: 4px"
        >
          <label
            v-for="(item, idx) in filteredSuggestions"
            :key="idx"
            class="list-group-item list-group-item-action py-2 suggestion-item border-0"
            :style="{ display: item.visible ? '' : 'none' }"
          >
            <input
              v-model="selectedValues"
              type="checkbox"
              class="form-check-input me-2"
              :value="item.value"
            />
            <span>{{ item.label }}</span>
          </label>
        </div>
      </div>
    </teleport>
  </th>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  columnKey: {
    type: String,
    required: true
  },
  thClass: {
    type: String,
    default: ''
  },
  value: {
    type: String,
    default: ''
  },
  suggestions: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: 'Значение...'
  },
  sortState: {
    type: String,
    default: null  // null, 'asc', or 'desc'
  },
  isActive: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['filter', 'sort', 'clear'])

const isOpen = ref(false)
const filterValue = ref(props.value)
const selectedValues = ref([])
const searchQuery = ref('')
const menuRef = ref(null)
const inputRef = ref(null)
const menuStyle = ref({})
const toggleButtonRef = ref(null)

const hasActiveFilter = computed(() => {
  return props.isActive
})

const selectedCount = computed(() => selectedValues.value.length)

const filteredSuggestions = computed(() => {
  if (!props.suggestions) return []

  const query = searchQuery.value.toLowerCase()
  return props.suggestions.map(item => ({
    value: item,
    label: item,
    visible: !query || item.toLowerCase().includes(query)
  }))
})

function toggleFilter(event) {
  isOpen.value = !isOpen.value

  if (isOpen.value) {
    toggleButtonRef.value = event.currentTarget
    nextTick(() => {
      positionMenu()
      if (inputRef.value) {
        inputRef.value.focus()
      }
    })
  }
}

function positionMenu() {
  if (!toggleButtonRef.value || !menuRef.value) return

  const toggleRect = toggleButtonRef.value.getBoundingClientRect()
  const menuWidth = 280
  const viewport = {
    width: window.innerWidth,
    height: window.innerHeight
  }

  const margin = 10
  let top = toggleRect.bottom + 4
  let left = toggleRect.left

  // Check horizontal bounds
  if (left + menuWidth > viewport.width - margin) {
    left = Math.max(margin, viewport.width - menuWidth - margin)
  }

  if (left < margin) {
    left = margin
  }

  // Check vertical bounds
  const menuHeight = 400
  if (top + menuHeight > viewport.height - margin) {
    const topPosition = toggleRect.top - menuHeight - 4
    if (topPosition >= margin) {
      top = topPosition
    }
  }

  menuStyle.value = {
    top: `${top}px`,
    left: `${left}px`
  }
}

function applyFilter() {
  let value = filterValue.value.trim()

  if (selectedValues.value.length > 0) {
    // Используем выбранные значения из чекбоксов
    if (selectedValues.value.length === 1) {
      emit('filter', props.columnKey, selectedValues.value[0])
    } else {
      const joinedValue = selectedValues.value.join('||')
      emit('filter', props.columnKey, joinedValue, true)
    }
  } else if (value) {
    // Используем введённое значение
    if (value.includes('||')) {
      const values = value.split('||').map(v => v.trim()).filter(v => v)
      if (values.length > 1) {
        emit('filter', props.columnKey, values.join('||'), true)
      } else if (values.length === 1) {
        emit('filter', props.columnKey, values[0])
      }
    } else {
      emit('filter', props.columnKey, value)
    }
  } else {
    clearFilter()
    return
  }

  isOpen.value = false
}

function sort(descending) {
  emit('sort', props.columnKey, descending)
  isOpen.value = false
}

function clearFilter() {
  filterValue.value = ''
  selectedValues.value = []
  emit('clear', props.columnKey)
  isOpen.value = false
}

function handleClickOutside(event) {
  if (
    isOpen.value &&
    menuRef.value &&
    !menuRef.value.contains(event.target) &&
    toggleButtonRef.value &&
    !toggleButtonRef.value.contains(event.target)
  ) {
    isOpen.value = false
  }
}

watch(selectedValues, (newVal) => {
  // Update filterValue display
  if (newVal.length === 1) {
    filterValue.value = newVal[0]
  } else if (newVal.length > 1) {
    filterValue.value = newVal.join(' || ')
  } else {
    filterValue.value = ''
  }
})

watch(() => props.value, (newVal) => {
  filterValue.value = newVal
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen.value) {
      isOpen.value = false
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.column-filter .dropdown-toggle {
  position: relative;
  z-index: 2;
}

.column-filter .btn-link:hover {
  text-decoration: none;
}

.column-filter .filter-active {
  color: var(--bs-primary, #0d6efd) !important;
}

.filter-menu-portal {
  position: fixed !important;
  z-index: 1060 !important;
  backdrop-filter: blur(10px);
  background: var(--pi-overlay-light, rgba(255, 255, 255, 0.95));
  border: 1px solid var(--pi-border-color, rgba(0, 0, 0, 0.1));
  box-shadow: 0 8px 24px var(--pi-shadow-color, rgba(0, 0, 0, 0.15));
  min-width: 280px;
  max-height: 400px;
  overflow-y: auto;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  border-radius: 0.375rem;
}

.filter-menu-portal.show {
  opacity: 1;
  pointer-events: auto;
}

.filter-menu-portal .form-control {
  background-color: var(--pi-input-bg, #ffffff);
  color: var(--pi-text-primary, #212529);
  border-color: var(--pi-input-border, #ced4da);
}

.filter-menu-portal .form-control:focus {
  border-color: var(--pi-input-focus-border, rgba(13, 110, 253, 0.5));
}

.filter-menu-portal .text-muted {
  color: var(--pi-text-secondary, #6c757d) !important;
}

.suggestion-item {
  cursor: pointer;
  user-select: none;
  transition: background-color 0.15s ease;
  border-bottom: 1px solid var(--pi-border-light, rgba(0, 0, 0, 0.05));
  background: var(--pi-bg-primary, #ffffff);
  color: var(--pi-text-primary, #212529);
}

.suggestion-item:hover {
  background-color: var(--pi-dropdown-hover, rgba(0, 123, 255, 0.1));
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestions-container {
  background: var(--pi-bg-primary, #ffffff);
  border-color: var(--pi-border-color, #dee2e6) !important;
}
</style>
