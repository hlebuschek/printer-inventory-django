<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="modal fade show d-block"
      tabindex="-1"
      aria-labelledby="columnModalLabel"
      aria-modal="true"
      role="dialog"
      @click.self="close"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="columnModalLabel">Выбрать столбцы</h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <div class="modal-body">
            <div
              v-for="column in allColumns"
              :key="column.key"
              class="form-check"
            >
              <input
                :id="`col-${column.key}`"
                v-model="selectedColumns"
                class="form-check-input"
                type="checkbox"
                :value="column.key"
                :disabled="column.disabled"
              />
              <label class="form-check-label" :for="`col-${column.key}`">
                {{ column.label }}
              </label>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-primary" @click="apply">
              Применить
            </button>
            <button type="button" class="btn btn-secondary" @click="close">
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal backdrop -->
    <div v-if="show" class="modal-backdrop fade show"></div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  visibleColumns: {
    type: Array,
    required: true
  },
  allColumns: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['update:show', 'update:visible-columns'])

const selectedColumns = ref([...props.visibleColumns])

// Watch for show prop changes to reset selected columns
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      selectedColumns.value = [...props.visibleColumns]
    }
  }
)

function apply() {
  // Ensure required columns are always included
  const requiredColumns = props.allColumns
    .filter(col => col.disabled)
    .map(col => col.key)

  const finalSelection = [...new Set([...selectedColumns.value, ...requiredColumns])]

  // Save to localStorage
  localStorage.setItem('visibleColumns', JSON.stringify(finalSelection))

  // Emit update
  emit('update:visible-columns', finalSelection)
  close()
}

function close() {
  emit('update:show', false)
}
</script>

<style scoped>
.modal {
  background: rgba(0, 0, 0, 0.5);
}
</style>
