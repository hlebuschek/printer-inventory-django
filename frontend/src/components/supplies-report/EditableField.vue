<template>
  <div class="editable-field" :class="stateClass">
    <textarea
      v-if="type === 'textarea'"
      :value="localValue"
      :rows="rows"
      :disabled="disabled || saving"
      :placeholder="placeholder"
      :class="['form-control', 'form-control-sm', 'editable-field-input']"
      @input="onInput"
      @blur="handleCommit"
      @keydown="handleKeydown"
    />
    <input
      v-else
      :type="type"
      :value="localValue"
      :disabled="disabled || saving"
      :placeholder="placeholder"
      :class="['form-control', 'form-control-sm', 'editable-field-input']"
      @input="onInput"
      @blur="handleCommit"
      @keydown="handleKeydown"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const SAVED_INDICATOR_MS = 1500
const ERROR_INDICATOR_MS = 2500

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'textarea' }, // textarea | text | number
  rows: { type: Number, default: 2 },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  saveFn: { type: Function, required: true }, // async (newValue) => any. Throws on error.
})

const emit = defineEmits(['update:modelValue'])

const localValue = ref(props.modelValue ?? '')
const original = ref(props.modelValue ?? '')
const saving = ref(false)
const saved = ref(false)
const error = ref(false)

watch(() => props.modelValue, (v) => {
  // Внешнее обновление (например, после refresh) — синхронизируем,
  // но только если значение реально другое (избегаем flicker после собственного save).
  if (saving.value) return
  const next = v ?? ''
  if (next === localValue.value) {
    original.value = next
    return
  }
  localValue.value = next
  original.value = next
})

function onInput(e) {
  localValue.value = e.target.value
  emit('update:modelValue', e.target.value)
}

function handleKeydown(e) {
  // Ctrl+Enter / Cmd+Enter в textarea — досрочно сохранить
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    e.target.blur()
  }
  // В однострочных input Enter тоже сохраняет
  if (e.key === 'Enter' && props.type !== 'textarea') {
    e.preventDefault()
    e.target.blur()
  }
}

async function handleCommit() {
  const cur = localValue.value
  if (cur === original.value) return
  if (saving.value) return

  saving.value = true
  saved.value = false
  error.value = false
  try {
    await props.saveFn(cur)
    original.value = cur
    saved.value = true
    setTimeout(() => { saved.value = false }, SAVED_INDICATOR_MS)
  } catch (e) {
    console.error('EditableField save error:', e)
    error.value = true
    setTimeout(() => { error.value = false }, ERROR_INDICATOR_MS)
    // Откат к предыдущему значению
    localValue.value = original.value
    emit('update:modelValue', original.value)
  } finally {
    saving.value = false
  }
}

const stateClass = computed(() => ({
  'is-saving': saving.value,
  'is-saved': saved.value,
  'is-error': error.value,
}))
</script>

<style scoped>
.editable-field {
  position: relative;
}

/* В обычном состоянии НЕ переопределяем фон/цвет — пусть Bootstrap
   сам разруливает light/dark тему через .form-control. */
.editable-field-input {
  transition: background-color 0.25s ease, border-color 0.25s ease;
}

.editable-field-input:focus {
  box-shadow: 0 0 0 0.15rem rgba(13, 110, 253, 0.18);
}

/* Иконка-индикатор справа (общее) */
.editable-field::after {
  position: absolute;
  top: 4px;
  right: 6px;
  font-size: 13px;
  pointer-events: none;
}

/* Состояния используют полупрозрачные цвета поверх Bootstrap-овского фона —
   читаемо и в светлой, и в тёмной теме. Цвет текста наследуется (var(--bs-body-color)). */

/* ── SAVING ── */
.editable-field.is-saving .editable-field-input {
  background-color: rgba(255, 193, 7, 0.22);
  border-color: rgba(255, 193, 7, 0.65);
}
.editable-field.is-saving::after {
  content: "💾";
  opacity: 0.85;
  animation: efRotate 1s linear infinite;
}

/* ── SAVED ── */
.editable-field.is-saved .editable-field-input {
  background-color: rgba(25, 135, 84, 0.22);
  border-color: rgba(25, 135, 84, 0.65);
  animation: efSavedFlash 1s ease-out;
}
.editable-field.is-saved::after {
  content: "✅";
  animation: efBounce 0.6s ease-out;
}

/* ── ERROR ── */
.editable-field.is-error .editable-field-input {
  background-color: rgba(220, 53, 69, 0.22);
  border-color: rgba(220, 53, 69, 0.7);
  animation: efShake 0.45s ease-out;
}
.editable-field.is-error::after {
  content: "❌";
}

@keyframes efRotate {
  from { transform: rotate(0); }
  to { transform: rotate(360deg); }
}
@keyframes efSavedFlash {
  0%   { filter: brightness(1.15); }
  60%  { filter: brightness(1.05); }
  100% { filter: none; }
}
@keyframes efBounce {
  0%, 20%, 50%, 80%, 100% { transform: scale(1); }
  40% { transform: scale(1.2); }
  60% { transform: scale(1.1); }
}
@keyframes efShake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-2px); }
  75% { transform: translateX(2px); }
}
</style>
