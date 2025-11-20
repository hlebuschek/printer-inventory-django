<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="modal fade show d-block"
      tabindex="-1"
      aria-labelledby="deleteModalLabel"
      aria-modal="true"
      role="dialog"
      @click.self="close"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="deleteModalLabel">
              Подтверждение удаления
            </h5>
            <button type="button" class="btn-close" @click="close"></button>
          </div>

          <div class="modal-body">
            <p v-if="printer">
              Вы уверены, что хотите удалить принтер с IP-адресом
              <strong>{{ printer.ip_address }}</strong>
              (Серийный №: <strong>{{ printer.serial_number }}</strong>)?
            </p>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="close">
              Отмена
            </button>
            <button type="button" class="btn btn-danger" @click="confirm">
              Удалить
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
const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  printer: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:show', 'confirm'])

function close() {
  emit('update:show', false)
}

function confirm() {
  emit('confirm')
  close()
}
</script>

<style scoped>
.modal {
  background: rgba(0, 0, 0, 0.5);
}
</style>
