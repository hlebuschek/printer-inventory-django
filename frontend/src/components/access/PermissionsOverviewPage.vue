<template>
  <div class="permissions-overview-page">
    <h1 class="h4 mb-3">
      <i class="bi bi-shield-check me-2"></i>Мои права
    </h1>

    <div class="table-responsive">
      <table class="table table-sm table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Приложение</th>
            <th class="text-center">Доступ</th>
            <th class="text-center">Просмотр</th>
            <th class="text-center">Добавление</th>
            <th class="text-center">Редактирование</th>
            <th class="text-center">Удаление</th>
            <th>Спец. права</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in apps" :key="app.code">
            <td class="fw-semibold">{{ app.name }}</td>
            <td class="text-center">
              <i class="bi" :class="app.access ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
            </td>
            <td class="text-center">
              <i class="bi" :class="app.can_view ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
            </td>
            <td class="text-center">
              <i class="bi" :class="app.can_add ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
            </td>
            <td class="text-center">
              <i class="bi" :class="app.can_edit ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
            </td>
            <td class="text-center">
              <i class="bi" :class="app.can_delete ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
            </td>
            <td>
              <ul v-if="app.special && Object.keys(app.special).length" class="mb-0 list-unstyled small">
                <li
                  v-for="(val, key) in app.special"
                  :key="key"
                  class="d-flex align-items-center gap-1"
                >
                  <i class="bi flex-shrink-0" :class="val ? 'bi-check-circle-fill text-success' : 'bi-dash-circle text-secondary'"></i>
                  <span :class="{ 'text-muted': !val }">{{ key }}</span>
                </li>
              </ul>
              <span v-else class="text-muted small">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-muted small">
      <i class="bi bi-info-circle me-1"></i>
      Права назначаются через группы в админ-панели. Обратитесь к администратору для изменения.
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  initialData: {
    type: Object,
    default: () => ({})
  }
})

const apps = props.initialData.apps || []
</script>
