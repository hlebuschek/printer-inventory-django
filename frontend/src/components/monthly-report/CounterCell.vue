<template>
  <td
    :class="cellClasses"
    :title="cellTitle"
  >
    <!-- Editable input -->
    <input
      v-if="editable"
      ref="inputRef"
      v-model="localValue"
      type="number"
      class="form-control form-control-sm counter-input"
      :disabled="isRestricted || saving"
      @blur="saveValue"
      @keypress.enter="saveValue"
    />

    <!-- Read-only display -->
    <span v-else>{{ value }}</span>

    <!-- Manual edit indicator -->
    <span v-if="isManual && !saving" class="badge bg-warning text-dark ms-1" title="Ручное редактирование">
      <i class="bi bi-pencil-fill"></i>
    </span>

    <!-- Auto value hint -->
    <div v-if="autoValue !== undefined && autoValue !== value && !saving" class="small text-muted">
      авто: {{ autoValue }}
    </div>
  </td>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
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
  }
})

const emit = defineEmits(['saved'])

const { showToast } = useToast()

const localValue = ref(props.value)
const saving = ref(false)
const inputRef = ref(null)

// Computed properties
const isRestricted = computed(() => {
  // Если это дубль и НЕ первый в группе, ограничиваем редактирование конечных счётчиков
  if (props.duplicateInfo && !props.duplicateInfo.is_first) {
    return props.field.endsWith('_end')
  }
  return false
})

const cellClasses = computed(() => {
  const classes = ['cell-editable']

  if (saving.value) {
    classes.push('saving')
  }

  if (isRestricted.value) {
    classes.push('restricted-by-dup')
  }

  return classes.join(' ')
})

const cellTitle = computed(() => {
  if (isRestricted.value) {
    return 'Редактирование ограничено: используются значения первого устройства в группе дублей'
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

// Methods
async function saveValue() {
  const newValue = parseInt(localValue.value) || 0

  // Не сохраняем, если значение не изменилось
  if (newValue === props.value) {
    return
  }

  // Ограничение для дублей
  if (isRestricted.value) {
    showToast('Ошибка', 'Редактирование ограничено для дублирующихся устройств', 'error')
    localValue.value = props.value
    return
  }

  saving.value = true

  try {
    const payload = {
      [props.field]: newValue
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
      emit('saved')
    } else {
      showToast('Ошибка', data.error || 'Не удалось сохранить значение', 'error')
      // Откатываем к предыдущему значению
      localValue.value = props.value
    }
  } catch (error) {
    console.error('Error saving counter:', error)
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

.counter-input {
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  transition: border-color 0.2s ease;
  background-color: #fff;
  border-color: rgba(0, 0, 0, 0.1);
}

.counter-input:focus {
  box-shadow: 0 0 0 0.15rem rgba(13, 110, 253, 0.12);
}

.counter-input:disabled {
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

/* Saving state */
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

@keyframes saving-pulse {
  0%, 100% {
    background-position: 0% 0%;
  }
  50% {
    background-position: 100% 0%;
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

/* Restricted by duplicates */
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
</style>
