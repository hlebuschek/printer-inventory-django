<template>
  <div class="okdesk-multiselect position-relative" ref="rootRef">
    <div
      class="form-control form-control-sm d-flex align-items-center flex-wrap gap-1 multiselect-control"
      :class="{ 'is-open': open }"
      @click="onControlClick"
    >
      <i class="bi bi-person text-muted me-1"></i>
      <template v-if="modelValue.length">
        <span
          v-for="v in modelValue"
          :key="v"
          class="badge text-bg-primary d-inline-flex align-items-center"
        >
          <span class="text-truncate" style="max-width: 140px;">{{ v }}</span>
          <button
            type="button"
            class="btn-close btn-close-white ms-1"
            style="font-size: 0.55em;"
            aria-label="Удалить"
            @click.stop="remove(v)"
          ></button>
        </span>
      </template>
      <span v-else class="text-muted small flex-grow-1">{{ placeholder }}</span>
      <i class="bi bi-chevron-down ms-auto text-muted small"></i>
    </div>

    <div v-if="open" class="multiselect-panel shadow border rounded">
      <div class="p-2 border-bottom bg-body-tertiary">
        <div class="input-group input-group-sm">
          <span class="input-group-text"><i class="bi bi-search"></i></span>
          <input
            ref="searchRef"
            v-model="search"
            type="text"
            class="form-control"
            placeholder="Поиск инициатора..."
            @keydown.esc="open = false"
          />
        </div>
        <div
          v-if="modelValue.length"
          class="d-flex justify-content-between align-items-center mt-2 small"
        >
          <span class="text-muted">Выбрано: {{ modelValue.length }}</span>
          <button
            type="button"
            class="btn btn-link btn-sm p-0"
            @click="clearAll"
          >
            Очистить
          </button>
        </div>
      </div>

      <div class="multiselect-list">
        <div v-if="!filtered.length" class="text-muted small text-center py-3">
          Ничего не найдено
        </div>
        <label
          v-for="opt in filtered"
          :key="opt"
          class="multiselect-item d-flex align-items-center gap-2 px-2 py-1"
        >
          <input
            type="checkbox"
            class="form-check-input m-0"
            :checked="selected.has(opt)"
            @change="toggleOne(opt)"
          />
          <span class="text-truncate">{{ opt }}</span>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Инициатор заявки' }
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const search = ref('')
const rootRef = ref(null)
const searchRef = ref(null)

const selected = computed(() => new Set(props.modelValue))

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.options
  return props.options.filter((o) => o.toLowerCase().includes(q))
})

function onControlClick(e) {
  // Не открывать панель повторно, если кликнули по кнопке-крестику чипа
  if (e.target.closest('.btn-close')) return
  open.value = !open.value
}

function toggleOne(opt) {
  const curr = new Set(props.modelValue)
  if (curr.has(opt)) curr.delete(opt)
  else curr.add(opt)
  emit('update:modelValue', Array.from(curr))
}

function remove(opt) {
  emit('update:modelValue', props.modelValue.filter((v) => v !== opt))
}

function clearAll() {
  emit('update:modelValue', [])
}

function onDocClick(e) {
  if (!rootRef.value) return
  if (!rootRef.value.contains(e.target)) open.value = false
}

watch(open, (v) => {
  if (v) nextTick(() => searchRef.value?.focus())
  else search.value = ''
})

onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>

<style scoped>
.multiselect-control {
  cursor: pointer;
  min-height: calc(1.5em + 0.5rem + 2px);
}
.multiselect-control.is-open {
  border-color: var(--bs-primary);
  box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.15);
}
.multiselect-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  min-width: 280px;
  max-width: 400px;
  background: var(--bs-body-bg);
  z-index: 1050;
}
.multiselect-list {
  max-height: 280px;
  overflow-y: auto;
  padding: 0.25rem 0;
}
.multiselect-item {
  cursor: pointer;
  user-select: none;
}
.multiselect-item:hover {
  background: var(--bs-tertiary-bg);
}
</style>
