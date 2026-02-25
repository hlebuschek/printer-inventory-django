<template>
  <div class="d-flex flex-wrap align-items-center gap-2 mb-4">
    <!-- Организация -->
    <div class="d-flex align-items-center gap-1">
      <label class="form-label mb-0 me-1 text-muted small">Организация:</label>
      <select
        class="form-select form-select-sm"
        style="min-width: 180px; max-width: 260px;"
        :value="modelOrgId"
        @change="$emit('update:modelOrgId', $event.target.value ? parseInt($event.target.value) : null)"
      >
        <option :value="null">Все организации</option>
        <option v-for="org in organizations" :key="org.id" :value="org.id">
          {{ org.name }}
        </option>
      </select>
    </div>

    <!-- Период -->
    <div class="btn-group btn-group-sm" role="group" aria-label="Период">
      <button
        v-for="p in periods"
        :key="p.value"
        type="button"
        class="btn"
        :class="modelPeriod === p.value ? 'btn-primary' : 'btn-outline-secondary'"
        @click="$emit('update:modelPeriod', p.value)"
      >
        {{ p.label }}
      </button>
    </div>

    <!-- Кнопка обновления -->
    <button
      type="button"
      class="btn btn-sm btn-outline-secondary ms-auto"
      :disabled="loading"
      @click="$emit('refresh')"
      title="Обновить данные"
    >
      <i class="bi" :class="loading ? 'bi-arrow-clockwise spin' : 'bi-arrow-clockwise'"></i>
      Обновить
    </button>
  </div>
</template>

<script setup>
defineProps({
  organizations: { type: Array, default: () => [] },
  modelOrgId: { type: Number, default: null },
  modelPeriod: { type: Number, default: 7 },
  loading: { type: Boolean, default: false },
})

defineEmits(['update:modelOrgId', 'update:modelPeriod', 'refresh'])

const periods = [
  { value: 7, label: '7 дней' },
  { value: 30, label: '30 дней' },
  { value: 90, label: '90 дней' },
]
</script>

<style scoped>
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
