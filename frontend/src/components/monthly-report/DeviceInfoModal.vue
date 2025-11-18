<template>
  <div
    ref="modalRef"
    class="modal fade"
    tabindex="-1"
    aria-labelledby="deviceInfoModalLabel"
    aria-hidden="true"
  >
    <div class="modal-dialog modal-sm modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header py-2">
          <h5 id="deviceInfoModalLabel" class="modal-title">Информация об устройстве</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
        </div>

        <div class="modal-body small">
          <div v-if="device">
            <div class="mb-2">
              <strong>Серийный №:</strong> {{ device.serial_number }}
            </div>
            <div class="mb-2">
              <strong>IP:</strong>
              <a
                v-if="device.device_ip"
                :href="`http://${device.device_ip}`"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ device.device_ip }}
              </a>
              <span v-else>—</span>
            </div>
            <div class="mb-2">
              <strong>Последний успешный опрос:</strong>
              {{ device.inventory_last_ok ? formatDate(device.inventory_last_ok) : '—' }}
            </div>
            <div
              v-if="hasManualFields(device)"
              class="alert alert-warning small mt-2 mb-0"
            >
              ⚠️ Есть поля с ручным редактированием
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const modalRef = ref(null)
const device = ref(null)
let bootstrapModal = null

onMounted(() => {
  // Initialize Bootstrap modal
  if (modalRef.value) {
    // eslint-disable-next-line no-undef
    bootstrapModal = new bootstrap.Modal(modalRef.value)
  }
})

/**
 * Show modal with device data
 */
function show(deviceData) {
  device.value = deviceData
  bootstrapModal?.show()
}

/**
 * Hide modal
 */
function hide() {
  bootstrapModal?.hide()
}

/**
 * Format date
 */
function formatDate(dateString) {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (e) {
    return '—'
  }
}

/**
 * Check if device has manually edited fields
 */
function hasManualFields(device) {
  return !!(
    device.a4_bw_end_manual ||
    device.a4_color_end_manual ||
    device.a3_bw_end_manual ||
    device.a3_color_end_manual
  )
}

defineExpose({
  show,
  hide
})
</script>

<style scoped>
/* Minimal styles for the simple modal */
</style>
