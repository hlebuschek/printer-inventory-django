<template>
  <div
    :class="cellClasses"
    :title="cellTitle"
  >
    <!-- Editable input -->
    <input
      v-if="editable"
      ref="inputRef"
      v-model="localValue"
      type="number"
      inputmode="numeric"
      :class="inputClasses"
      :disabled="isDisabled"
      min="0"
      max="9999999"
      step="1"
      @input="handleInput"
      @blur="handleBlur"
      @keydown="handleKeydown"
      @paste="handlePaste"
    />

    <!-- Read-only display -->
    <span v-else>{{ value }}</span>

    <!-- Autosave progress bar -->
    <div v-if="showProgress" class="save-progress-container">
      <div class="save-progress-bar" :style="{ width: progressWidth + '%' }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useToast } from '../../composables/useToast'

const props = defineProps({
  reportId: {
    type: Number,
    required: true
  },
  field: {
    type: String,
    required: true
  },
  value: {
    type: Number,
    default: 0
  },
  editable: {
    type: Boolean,
    default: false
  },
  isManual: {
    type: Boolean,
    default: false
  },
  autoValue: {
    type: Number,
    default: undefined
  },
  duplicateInfo: {
    type: Object,
    default: null
  },
  allowed: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['saved'])

const { showToast } = useToast()

const localValue = ref(props.value)
const saving = ref(false)
const saved = ref(false)
const error = ref(false)
const inputRef = ref(null)
const showProgress = ref(false)
const progressWidth = ref(100)

// Autosave timer
let saveTimeout = null
let progressInterval = null
const AUTOSAVE_DELAY = 2000 // 2 seconds

// Computed properties
const isRestricted = computed(() => {
  // Если это дубль и НЕ первый в группе, ограничиваем редактирование конечных счётчиков
  if (props.duplicateInfo && !props.duplicateInfo.is_first) {
    return props.field.endsWith('_end')
  }
  return false
})

const isDisabled = computed(() => {
  return isRestricted.value || !props.allowed || saving.value
})

const inputClasses = computed(() => {
  const classes = ['form-control', 'form-control-sm', 'text-end', 'counter-input']

  if (props.isManual) {
    classes.push('manual-field')
  }

  return classes.join(' ')
})

const cellClasses = computed(() => {
  const classes = ['cell-editable']

  if (saving.value) {
    classes.push('saving')
  }

  if (saved.value) {
    classes.push('saved')
  }

  if (error.value) {
    classes.push('error')
  }

  if (isRestricted.value) {
    classes.push('restricted-by-dup')
  }

  // Подсветка ручного редактирования
  if (props.isManual) {
    classes.push('manual-edited')
  }

  return classes.join(' ')
})

const cellTitle = computed(() => {
  if (!props.allowed) {
    return 'Редактирование запрещено для данного формата бумаги'
  }
  if (isRestricted.value) {
    return 'Редактирование ограничено: используются значения первого устройства в группе дублей'
  }
  if (props.isManual && props.autoValue !== undefined) {
    return `Поле отредактировано вручную. Авто: ${props.autoValue}`
  }
  if (props.isManual) {
    return 'Значение отредактировано вручную'
  }
  if (props.autoValue !== undefined && props.autoValue !== props.value) {
    return `Автоматическое значение: ${props.autoValue}`
  }
  return ''
})

// Watch for external value changes
watch(() => props.value, (newValue) => {
  localValue.value = newValue
})

// Cleanup on unmount
onUnmounted(() => {
  stopAutosaveTimer()
})

// Methods
/**
 * Start autosave countdown with progress bar
 */
function startAutosaveTimer() {
  stopAutosaveTimer()

  showProgress.value = true
  progressWidth.value = 100

  const startTime = Date.now()

  // Update progress bar
  progressInterval = setInterval(() => {
    const elapsed = Date.now() - startTime
    const remaining = AUTOSAVE_DELAY - elapsed
    progressWidth.value = Math.max(0, (remaining / AUTOSAVE_DELAY) * 100)

    if (remaining <= 0) {
      clearInterval(progressInterval)
    }
  }, 50)

  // Schedule save
  saveTimeout = setTimeout(() => {
    showProgress.value = false
    saveValue()
  }, AUTOSAVE_DELAY)
}

/**
 * Stop autosave timer
 */
function stopAutosaveTimer() {
  if (saveTimeout) {
    clearTimeout(saveTimeout)
    saveTimeout = null
  }
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
  showProgress.value = false
  progressWidth.value = 100
}

/**
 * Handle input event - start autosave timer
 */
function handleInput() {
  const newValue = parseInt(localValue.value) || 0

  // Validate max value
  if (newValue > 9999999) {
    showToast('Ошибка', 'Значение не может быть больше 9,999,999', 'error')
    localValue.value = 9999999
    return
  }

  // Don't start timer if value hasn't changed
  if (newValue === props.value) {
    stopAutosaveTimer()
    return
  }

  // Start autosave countdown
  startAutosaveTimer()
}

/**
 * Handle blur event - save immediately
 */
function handleBlur() {
  stopAutosaveTimer()

  const newValue = parseInt(localValue.value) || 0
  if (newValue !== props.value) {
    saveValue()
  }
}

/**
 * Валидация ввода с клавиатуры
 * Блокируем: e, E, +, -, .
 */
function handleKeydown(event) {
  // Enter - save immediately
  if (event.key === 'Enter') {
    event.preventDefault()
    stopAutosaveTimer()
    saveValue()
    return
  }

  const invalidKeys = ['e', 'E', '+', '-', '.', ',']

  if (invalidKeys.includes(event.key)) {
    event.preventDefault()
    return
  }

  // Разрешаем: цифры, Backspace, Delete, Arrow keys, Tab, Escape
  const allowedKeys = [
    'Backspace', 'Delete', 'Tab', 'Escape',
    'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
    'Home', 'End'
  ]

  const isDigit = /^[0-9]$/.test(event.key)
  const isAllowedKey = allowedKeys.includes(event.key)
  const isCtrlCmd = event.ctrlKey || event.metaKey // Ctrl+C, Ctrl+V, etc.

  if (!isDigit && !isAllowedKey && !isCtrlCmd) {
    event.preventDefault()
  }
}

/**
 * Валидация вставки из буфера обмена
 */
function handlePaste(event) {
  event.preventDefault()

  const pastedText = event.clipboardData.getData('text')
  const onlyDigits = pastedText.replace(/\D/g, '') // Удаляем все нецифровые символы

  if (onlyDigits) {
    let pastedValue = parseInt(onlyDigits)

    // Validate max value
    if (pastedValue > 9999999) {
      showToast('Ошибка', 'Значение не может быть больше 9,999,999', 'error')
      pastedValue = 9999999
    }

    localValue.value = pastedValue
    // Trigger autosave
    handleInput()
  }
}

async function saveValue() {
  const newValue = parseInt(localValue.value) || 0

  // Не сохраняем, если значение не изменилось
  if (newValue === props.value) {
    return
  }

  // Проверка разрешений
  if (!props.allowed) {
    showToast('Ошибка', 'Редактирование запрещено для данного формата бумаги', 'error')
    localValue.value = props.value
    return
  }

  // Ограничение для дублей
  if (isRestricted.value) {
    showToast('Ошибка', 'Редактирование ограничено для дублирующихся устройств', 'error')
    localValue.value = props.value
    return
  }

  // Сбрасываем предыдущие состояния
  saved.value = false
  error.value = false
  saving.value = true

  try {
    const payload = {
      fields: {
        [props.field]: newValue
      }
    }

    const response = await fetch(`/monthly-report/api/update-counters/${props.reportId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()

    if (data.ok) {
      // Успешное сохранение
      saved.value = true
      setTimeout(() => {
        saved.value = false
      }, 2000)

      // Emit event with updated data for parent component
      emit('saved', {
        reportId: props.reportId,
        field: props.field,
        value: newValue,
        report: data.report
      })
    } else {
      // Ошибка сохранения
      error.value = true
      setTimeout(() => {
        error.value = false
      }, 3000)

      showToast('Ошибка', data.error || 'Не удалось сохранить значение', 'error')
      // Откатываем к предыдущему значению
      localValue.value = props.value
    }
  } catch (err) {
    console.error('Error saving counter:', err)

    error.value = true
    setTimeout(() => {
      error.value = false
    }, 3000)

    showToast('Ошибка', 'Не удалось сохранить значение', 'error')
    localValue.value = props.value
  } finally {
    saving.value = false
  }
}

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}
</script>

<style scoped>
.cell-editable {
  position: relative;
}

.cell-editable:hover .form-control {
  border-color: rgba(13, 110, 253, 0.35);
}

.counter-input {
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  transition: border-color 0.2s ease;
  padding-right: 2rem;
  background-color: #fff;
  border-color: rgba(0, 0, 0, 0.1);
}

.counter-input:focus {
  box-shadow: 0 0 0 0.15rem rgba(13, 110, 253, 0.12);
}

.counter-input:disabled,
.counter-input[disabled] {
  background: #f6f6f6;
  cursor: not-allowed;
}

/* Убираем стрелки у number input */
.counter-input[type="number"]::-webkit-inner-spin-button,
.counter-input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.counter-input[type="number"] {
  -moz-appearance: textfield;
}

/* =========================
   SAVING/SAVED/ERROR STATES
   ========================= */
.cell-editable.saving {
  background: linear-gradient(90deg, #fff3cd 0%, #fff3cd 50%, #ffffff 51%, #ffffff 100%);
  background-size: 200% 100%;
  animation: saving-pulse 1s ease-in-out infinite;
}

.cell-editable.saving::after {
  content: "💾";
  position: absolute;
  right: 0.35rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  opacity: 0.8;
  animation: rotate 1s linear infinite;
}

.cell-editable.saved {
  background: linear-gradient(90deg, #d1e7dd 0%, #ffffff 100%);
  animation: saved-flash 0.6s ease-out;
}

.cell-editable.saved::after {
  content: "✅";
  position: absolute;
  right: 0.35rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  animation: bounce 0.6s ease-out;
}

.cell-editable.error {
  background: linear-gradient(90deg, #f8d7da 0%, #ffffff 100%);
  animation: error-shake 0.6s ease-out;
}

.cell-editable.error::after {
  content: "❌";
  position: absolute;
  right: 0.35rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  animation: shake 0.6s ease-out;
}

@keyframes saving-pulse {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@keyframes rotate {
  from {
    transform: translateY(-50%) rotate(0deg);
  }
  to {
    transform: translateY(-50%) rotate(360deg);
  }
}

@keyframes saved-flash {
  0% { background: #d1e7dd; transform: scale(1); }
  50% { background: #a3d9a4; transform: scale(1.02); }
  100% { background: #ffffff; transform: scale(1); }
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% { transform: translateY(-50%) scale(1); }
  40% { transform: translateY(-50%) scale(1.2); }
  60% { transform: translateY(-50%) scale(1.1); }
}

@keyframes error-shake {
  0%, 100% { background: #ffffff; transform: translateX(0); }
  25% { background: #f8d7da; transform: translateX(-2px); }
  75% { background: #f8d7da; transform: translateX(2px); }
}

@keyframes shake {
  0%, 100% { transform: translateY(-50%) translateX(0); }
  25% { transform: translateY(-50%) translateX(-2px); }
  75% { transform: translateY(-50%) translateX(2px); }
}

/* =========================
   MANUAL EDITED
   ========================= */
.cell-editable.manual-edited {
  position: relative;
  background-color: #fff3cd !important;
  border-left: 3px solid #ffc107 !important;
}

.counter-input.manual-field {
  background-color: #fff3cd !important;
  border-color: #ffc107 !important;
}

.counter-input.manual-field:focus {
  border-color: #ff8c00 !important;
  box-shadow: 0 0 0 0.15rem rgba(255, 193, 7, 0.25) !important;
}

.cell-editable.became-manual {
  animation: becameManual 2s ease-out;
}

@keyframes becameManual {
  0% {
    background-color: #d1ecf1;
    border-left-color: #0dcaf0;
    transform: scale(1);
  }
  30% {
    background-color: #ffeaa7;
    border-left-color: #fdcb6e;
    transform: scale(1.02);
  }
  100% {
    background-color: #fff3cd;
    border-left-color: #ffc107;
    transform: scale(1);
  }
}

/* =========================
   RESTRICTED BY DUPLICATES
   ========================= */
.cell-editable.restricted-by-dup {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-left: 3px solid #6c757d;
}

.cell-editable.restricted-by-dup input[disabled] {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  color: #6c757d;
  border-color: #ced4da;
  cursor: not-allowed;
}

/* =========================
   AUTOSAVE PROGRESS BAR
   ========================= */
.save-progress-container {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(0, 0, 0, 0.05);
  overflow: hidden;
  z-index: 5;
  border-radius: 0 0 0.375rem 0.375rem;
}

.save-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #ffc107, #fd7e14);
  transition: width 50ms linear;
  box-shadow: 0 0 8px rgba(255, 193, 7, 0.5);
}
</style>
