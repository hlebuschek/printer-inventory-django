<template>
  <div>
    <div class="fw-semibold small text-uppercase text-muted mb-1">{{ title }}</div>
    <div v-if="!rows.length" class="text-muted small">Нет данных</div>
    <table v-else class="table table-sm align-middle mb-0">
      <thead>
        <tr>
          <th>{{ firstColumn }}</th>
          <th class="text-end">Заявок</th>
          <th class="text-end">Просрочено</th>
          <th class="text-end" title="Рабочие часы по графику объекта">Простой, ч</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.label">
          <td>{{ row.label }}</td>
          <td class="text-end">{{ row.total }}</td>
          <td class="text-end">
            <span :class="row.overdue ? 'text-danger' : 'text-muted'">
              {{ row.overdue || '—' }}
            </span>
            <span v-if="row.overdue" class="text-muted small ms-1">{{ row.overdue_share }}%</span>
          </td>
          <td class="text-end">
            {{ row.downtime_hours || '—' }}
            <span v-if="row.downtime_hours" class="text-muted small ms-1">{{ row.avg_downtime_hours }} ср.</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  firstColumn: { type: String, required: true },
  rows: { type: Array, default: () => [] }
})
</script>
