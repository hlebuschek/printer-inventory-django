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
        <!-- Sort and Actions -->
        <div class="d-flex gap-1 mb-2 flex-wrap">
          <button v-if="sortable" class="btn btn-outline-secondary btn-sm" type="button" title="Сортировать по возрастанию" @click.stop="sort(false)">
            ↑
          </button>
          <button v-if="sortable" class="btn btn-outline-secondary btn-sm" type="button" title="Сортировать по убыванию" @click.stop="sort(true)">
            ↓
          </button>
          <button class="btn btn-link btn-sm text-danger ms-auto" type="button" @click.stop="clearFilter">
            Сброс
          </button>
        </div>

        <!-- Condition -->
        <select v-if="ops" v-model="opValue" class="form-select form-select-sm mb-2">
          <option v-for="o in opOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>

        <!-- Filter Input: вводимый текст сужает список ниже, Enter/OK отправляет фильтр -->
        <div class="input-group input-group-sm mb-2">
          <input
            ref="inputRef"
            v-model="filterValue"
            type="text"
            class="form-control"
            :placeholder="isRange ? 'От...' : placeholder"
            @keypress.enter="applyFilter"
          />
          <input
            v-if="isRange"
            v-model="filterValueTo"
            type="text"
            class="form-control"
            placeholder="До..."
            @keypress.enter="applyFilter"
          />
          <button class="btn btn-primary" type="button" @click.stop="applyFilter">OK</button>
        </div>

        <!-- Suggestions (if provided) -->
        <template v-if="suggestions && suggestions.length > 0">
          <div class="mb-1 small text-muted d-flex align-items-center flex-wrap gap-2">
            <span>
              Выбрано: <span class="selected-count">{{ selectedCount }}</span> из
              <span>{{ visibleCount }}</span>
            </span>
            <label v-if="ops" class="d-flex align-items-center gap-1 ms-auto exclude-toggle" title="Показать всё, кроме выбранного">
              <input v-model="excludeMode" type="checkbox" class="form-check-input m-0" />
              <span>Исключить</span>
            </label>
          </div>

          <div class="suggestions-container" style="max-height: 240px; overflow-y: auto; border-radius: 4px">
            <label class="list-group-item list-group-item-action py-2 suggestion-item border-0 fw-semibold">
              <input
                ref="selectAllRef"
                type="checkbox"
                class="form-check-input me-2"
                :checked="allVisibleSelected"
                :indeterminate="someVisibleSelected && !allVisibleSelected"
                @change="toggleSelectAll"
              />
              <span>(Выделить все)</span>
            </label>
            <label
              v-if="ops && dataType === 'text' && !listQuery"
              class="list-group-item list-group-item-action py-2 suggestion-item border-0 fst-italic"
            >
              <input
                v-model="selectedValues"
                type="checkbox"
                class="form-check-input me-2"
                :value="EMPTY_SENTINEL"
              />
              <span>(Пустые)</span>
            </label>
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
        </template>
      </div>
    </teleport>
  </th>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'

const EMPTY_SENTINEL = '__empty__'

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
  currentMulti: {
    type: String,
    default: ''
  },
  currentOp: {
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
  },
  sortable: {
    type: Boolean,
    default: true
  },
  // Условия (содержит/не содержит/...) и "(Пустые)"/"Исключить" — выключаются
  // для спец-колонок, чьи фильтры бэкенд обрабатывает отдельной логикой
  ops: {
    type: Boolean,
    default: true
  },
  dataType: {
    type: String,
    default: 'text'  // 'text' | 'number'
  }
})

const emit = defineEmits(['filter', 'sort', 'clear'])

const TEXT_OPS = [
  { value: 'contains', label: 'Содержит' },
  { value: 'ncontains', label: 'Не содержит' },
  { value: 'eq', label: 'Равно' },
  { value: 'startswith', label: 'Начинается с' }
]

const NUMBER_OPS = [
  { value: 'eq', label: '= (равно)' },
  { value: 'gt', label: '> (больше)' },
  { value: 'gte', label: '≥ (больше или равно)' },
  { value: 'lt', label: '< (меньше)' },
  { value: 'lte', label: '≤ (меньше или равно)' },
  { value: 'range', label: 'Между' }
]

const isOpen = ref(false)
const filterValue = ref('')
const filterValueTo = ref('')
const selectedValues = ref([])
const excludeMode = ref(false)
const menuRef = ref(null)
const inputRef = ref(null)
const menuStyle = ref({})
const toggleButtonRef = ref(null)

const defaultOp = computed(() => (props.dataType === 'number' ? 'eq' : 'contains'))
const opOptions = computed(() => (props.dataType === 'number' ? NUMBER_OPS : TEXT_OPS))
const opValue = ref('contains')
const isRange = computed(() => props.ops && opValue.value === 'range')

const hasActiveFilter = computed(() => {
  return props.isActive
})

const selectedCount = computed(() => selectedValues.value.length)

// Единое поле: вводимое значение одновременно сужает список (как поиск в Excel)
// Пробелы не обрезаем: "иркутск " (с пробелом) не должен матчить "Иркутская"
const listQuery = computed(() => (isRange.value ? '' : filterValue.value.toLowerCase()))

const filteredSuggestions = computed(() => {
  if (!props.suggestions) return []

  const query = listQuery.value
  // Выбранные значения, выпавшие из choices из-за кросс-фильтрации, показываем сверху
  const known = new Set(props.suggestions)
  const extras = selectedValues.value.filter(v => v !== EMPTY_SENTINEL && !known.has(v))
  return [...extras, ...props.suggestions].map(item => ({
    value: item,
    label: String(item),
    visible: !query || String(item).toLowerCase().includes(query)
  }))
})

const visibleSuggestionValues = computed(() =>
  filteredSuggestions.value.filter(i => i.visible).map(i => i.value)
)

const visibleCount = computed(() => visibleSuggestionValues.value.length)

const allVisibleSelected = computed(() => {
  const visible = visibleSuggestionValues.value
  if (!visible.length) return false
  const selected = new Set(selectedValues.value)
  return visible.every(v => selected.has(v))
})

const someVisibleSelected = computed(() => {
  const selected = new Set(selectedValues.value)
  return visibleSuggestionValues.value.some(v => selected.has(v))
})

function toggleSelectAll() {
  const visible = visibleSuggestionValues.value
  if (allVisibleSelected.value) {
    const visibleSet = new Set(visible)
    selectedValues.value = selectedValues.value.filter(v => !visibleSet.has(v))
  } else {
    const merged = new Set(selectedValues.value)
    visible.forEach(v => merged.add(v))
    selectedValues.value = Array.from(merged)
  }
}

function matchesTextFilter(text) {
  const needle = props.value.toLowerCase()
  const t = text.toLowerCase()
  switch (props.currentOp) {
    case 'ncontains':
      return !t.includes(needle)
    case 'eq':
      return t === needle
    case 'startswith':
      return t.startsWith(needle)
    default:
      return t.includes(needle)
  }
}

function syncFromProps() {
  excludeMode.value = props.currentOp === 'nin'
  selectedValues.value = props.currentMulti
    ? props.currentMulti.split('||').map(s => s.trim()).filter(Boolean)
    : []
  filterValue.value = ''
  filterValueTo.value = ''
  opValue.value = defaultOp.value

  if (!props.value) return

  if (props.currentOp === 'range' && props.value.includes('..')) {
    const [from, to] = props.value.split('..')
    filterValue.value = from
    filterValueTo.value = to ?? ''
    opValue.value = 'range'
    return
  }

  if (props.dataType !== 'number' && props.suggestions?.length) {
    // Текстовый фильтр показываем как в Excel: весь список, подходящие значения — с галочками
    selectedValues.value = props.suggestions.filter(v => matchesTextFilter(String(v)))
    return
  }

  filterValue.value = props.value
  if (props.currentOp && props.currentOp !== 'nin') {
    opValue.value = props.currentOp
  }
}

function toggleFilter(event) {
  isOpen.value = !isOpen.value

  if (isOpen.value) {
    syncFromProps()
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
  // Выбор чекбоксами — точное совпадение по списку (как в Excel)
  if (selectedValues.value.length > 0) {
    emit('filter', props.columnKey, selectedValues.value.join('||'), true, excludeMode.value ? 'nin' : '')
    isOpen.value = false
    return
  }

  // Текст не обрезаем: пробел в "иркутск " — осознанная граница слова (как в Excel)
  const raw = filterValue.value
  const value = raw.trim()

  if (isRange.value) {
    const to = filterValueTo.value.trim()
    if (!value || !to) return
    emit('filter', props.columnKey, `${value}..${to}`, false, 'range')
    isOpen.value = false
    return
  }

  if (value) {
    if (raw.includes('||')) {
      // Ручной ввод нескольких значений через ||
      const values = raw.split('||').map(v => v.trim()).filter(v => v)
      if (values.length > 1) {
        emit('filter', props.columnKey, values.join('||'), true, excludeMode.value ? 'nin' : '')
      } else if (values.length === 1) {
        emit('filter', props.columnKey, values[0], false, opValue.value !== defaultOp.value ? opValue.value : '')
      }
    } else {
      const sendValue = props.dataType === 'number' ? value : raw
      emit('filter', props.columnKey, sendValue, false, opValue.value !== defaultOp.value ? opValue.value : '')
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
  filterValueTo.value = ''
  selectedValues.value = []
  excludeMode.value = false
  opValue.value = defaultOp.value
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

function handleScroll(event) {
  if (!isOpen.value) return
  // Прокрутка внутри самого меню не двигает кнопку-воронку
  if (menuRef.value && menuRef.value.contains(event.target)) return
  positionMenu()
}

function handleKeydown(e) {
  if (e.key === 'Escape' && isOpen.value) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  // capture: горизонтальный скролл таблицы не всплывает до document,
  // а меню у нас position:fixed — двигаем его вслед за колонкой
  window.addEventListener('scroll', handleScroll, true)
  window.addEventListener('resize', handleScroll)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('scroll', handleScroll, true)
  window.removeEventListener('resize', handleScroll)
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
  max-height: 460px;
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

.filter-menu-portal .form-control,
.filter-menu-portal .form-select {
  background-color: var(--pi-input-bg, #ffffff);
  color: var(--pi-text-primary, #212529);
  border-color: var(--pi-input-border, #ced4da);
}

.filter-menu-portal .form-control:focus,
.filter-menu-portal .form-select:focus {
  border-color: var(--pi-input-focus-border, rgba(13, 110, 253, 0.5));
}

.filter-menu-portal .text-muted {
  color: var(--pi-text-secondary, #6c757d) !important;
}

.exclude-toggle {
  cursor: pointer;
  white-space: nowrap;
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
