<template>
  <div class="contract-device-table">
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
      <p class="mt-2">Загрузка устройств...</p>
    </div>

    <div v-else-if="!devices.length" class="alert alert-info">
      <i class="bi bi-info-circle me-2"></i>
      Устройства не найдены. Попробуйте изменить параметры фильтрации.
    </div>

    <div v-else class="table-responsive">
      <table class="table table-hover table-sm">
        <thead class="table-light">
          <tr>
            <th style="width: 5%">#</th>
            <th style="width: 15%">Организация</th>
            <th style="width: 10%">Город</th>
            <th style="width: 15%">Адрес</th>
            <th style="width: 5%">Каб.</th>
            <th style="width: 15%">Модель</th>
            <th style="width: 10%">S/N</th>
            <th style="width: 8%">Статус</th>
            <th style="width: 7%">Месяц</th>
            <th style="width: 10%">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(device, index) in devices" :key="device.id">
            <td>{{ index + 1 }}</td>
            <td>{{ device.organization }}</td>
            <td>{{ device.city }}</td>
            <td>{{ device.address }}</td>
            <td>{{ device.room_number }}</td>
            <td>
              <strong>{{ device.manufacturer }}</strong> {{ device.model }}
            </td>
            <td>
              <code>{{ device.serial_number || '—' }}</code>
            </td>
            <td>
              <span
                class="badge"
                :style="{ backgroundColor: device.status_color, color: '#fff' }"
              >
                {{ device.status }}
              </span>
            </td>
            <td>
              <small>{{ device.service_start_month || '—' }}</small>
            </td>
            <td>
              <div class="btn-group btn-group-sm" role="group">
                <button
                  class="btn btn-outline-primary"
                  :title="'Редактировать'"
                  @click="$emit('edit', device)"
                >
                  <i class="bi bi-pencil"></i>
                </button>
                <button
                  class="btn btn-outline-danger"
                  :title="'Удалить'"
                  @click="$emit('delete', device)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Комментарии -->
    <div v-if="devices.length" class="mt-2">
      <small class="text-muted">
        <i class="bi bi-info-circle me-1"></i>
        Всего устройств: {{ devices.length }}
      </small>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  devices: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['edit', 'delete'])
</script>

<style scoped>
.contract-device-table {
  background: white;
  border-radius: 0.375rem;
  box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
}

.table {
  margin-bottom: 0;
}

.table th {
  font-weight: 600;
  font-size: 0.875rem;
  color: #495057;
  border-bottom: 2px solid #dee2e6;
}

.table td {
  vertical-align: middle;
  font-size: 0.875rem;
}

.table tbody tr:hover {
  background-color: rgba(0, 123, 255, 0.05);
}

code {
  font-size: 0.8125rem;
  padding: 0.125rem 0.25rem;
  background: #f8f9fa;
  border-radius: 0.25rem;
}

.badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}

.btn-group-sm .btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}
</style>
