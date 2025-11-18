<template>
  <div
    ref="modalRef"
    class="modal fade"
    tabindex="-1"
    aria-labelledby="deviceInfoModalLabel"
    aria-hidden="true"
  >
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 id="deviceInfoModalLabel" class="modal-title">
            <i class="bi bi-info-circle"></i> Информация об устройстве
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>

        <div class="modal-body">
          <div v-if="device" class="device-info">
            <!-- Основная информация -->
            <div class="info-section">
              <h6 class="section-title">Основная информация</h6>
              <div class="row g-2">
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Организация:</span>
                    <span class="info-value">{{ device.organization }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Филиал:</span>
                    <span class="info-value">{{ device.branch }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Город:</span>
                    <span class="info-value">{{ device.city }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Адрес:</span>
                    <span class="info-value">{{ device.address }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Устройство -->
            <div class="info-section">
              <h6 class="section-title">Устройство</h6>
              <div class="row g-2">
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Модель:</span>
                    <span class="info-value">{{ device.equipment_model }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Серийный №:</span>
                    <span class="info-value fw-bold">{{ device.serial_number }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Инвентарный №:</span>
                    <span class="info-value">{{ device.inventory_number || '—' }}</span>
                  </div>
                </div>
                <div class="col-md-6" v-if="device.ip_address">
                  <div class="info-item">
                    <span class="info-label">IP адрес:</span>
                    <span class="info-value">{{ device.ip_address }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Последний опрос -->
            <div v-if="device.last_poll_date" class="info-section">
              <h6 class="section-title">Последний опрос</h6>
              <div class="row g-2">
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Дата опроса:</span>
                    <span class="info-value">{{ formatDate(device.last_poll_date) }}</span>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="info-item">
                    <span class="info-label">Статус:</span>
                    <span :class="getPollStatusClass(device.last_poll_status)">
                      {{ getPollStatusText(device.last_poll_status) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Счетчики -->
            <div class="info-section">
              <h6 class="section-title">Счетчики</h6>
              <div class="table-responsive">
                <table class="table table-sm table-bordered">
                  <thead class="table-light">
                    <tr>
                      <th>Тип</th>
                      <th>Начало</th>
                      <th>Конец</th>
                      <th>Отпечатано</th>
                      <th>Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>A4 ч/б</td>
                      <td>{{ device.a4_bw_start }}</td>
                      <td>{{ device.a4_bw_end }}</td>
                      <td class="fw-bold">{{ device.a4_bw_end - device.a4_bw_start }}</td>
                      <td>
                        <span v-if="device.a4_bw_end_manual" class="badge bg-warning text-dark">
                          <i class="bi bi-pencil-fill"></i> Ручное
                        </span>
                        <span v-else class="badge bg-success">
                          <i class="bi bi-check-circle-fill"></i> Авто
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td>A4 цветн</td>
                      <td>{{ device.a4_color_start }}</td>
                      <td>{{ device.a4_color_end }}</td>
                      <td class="fw-bold">{{ device.a4_color_end - device.a4_color_start }}</td>
                      <td>
                        <span v-if="device.a4_color_end_manual" class="badge bg-warning text-dark">
                          <i class="bi bi-pencil-fill"></i> Ручное
                        </span>
                        <span v-else class="badge bg-success">
                          <i class="bi bi-check-circle-fill"></i> Авто
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td>A3 ч/б</td>
                      <td>{{ device.a3_bw_start }}</td>
                      <td>{{ device.a3_bw_end }}</td>
                      <td class="fw-bold">{{ device.a3_bw_end - device.a3_bw_start }}</td>
                      <td>
                        <span v-if="device.a3_bw_end_manual" class="badge bg-warning text-dark">
                          <i class="bi bi-pencil-fill"></i> Ручное
                        </span>
                        <span v-else class="badge bg-success">
                          <i class="bi bi-check-circle-fill"></i> Авто
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td>A3 цветн</td>
                      <td>{{ device.a3_color_start }}</td>
                      <td>{{ device.a3_color_end }}</td>
                      <td class="fw-bold">{{ device.a3_color_end - device.a3_color_start }}</td>
                      <td>
                        <span v-if="device.a3_color_end_manual" class="badge bg-warning text-dark">
                          <i class="bi bi-pencil-fill"></i> Ручное
                        </span>
                        <span v-else class="badge bg-success">
                          <i class="bi bi-check-circle-fill"></i> Авто
                        </span>
                      </td>
                    </tr>
                    <tr class="table-info">
                      <td colspan="3" class="text-end fw-bold">Всего отпечатано:</td>
                      <td class="fw-bold fs-5">{{ device.total_prints }}</td>
                      <td></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Дубликаты -->
            <div v-if="device.duplicate_info" class="info-section">
              <h6 class="section-title">
                <i class="bi bi-exclamation-triangle text-warning"></i> Дубликат
              </h6>
              <div class="alert alert-warning mb-0">
                <p class="mb-0">
                  Устройство {{ device.duplicate_info.position + 1 }} из {{ device.duplicate_info.total_in_group }}
                  с одинаковым серийным номером
                </p>
                <p v-if="!device.duplicate_info.is_first" class="mb-0 small">
                  Конечные счетчики берутся из первого устройства в группе
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            Закрыть
          </button>
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
  const date = new Date(dateString)
  return date.toLocaleString('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Get poll status class
 */
function getPollStatusClass(status) {
  const classes = {
    success: 'badge bg-success',
    warning: 'badge bg-warning text-dark',
    error: 'badge bg-danger'
  }
  return classes[status] || 'badge bg-secondary'
}

/**
 * Get poll status text
 */
function getPollStatusText(status) {
  const texts = {
    success: 'Успешно',
    warning: 'Предупреждение',
    error: 'Ошибка'
  }
  return texts[status] || 'Неизвестно'
}

defineExpose({
  show,
  hide
})
</script>

<style scoped>
.device-info {
  font-size: 0.95rem;
}

.info-section {
  margin-bottom: 1.5rem;
}

.info-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: #495057;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #dee2e6;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-label {
  font-weight: 500;
  color: #6c757d;
  margin-right: 1rem;
}

.info-value {
  color: #212529;
  text-align: right;
}
</style>
