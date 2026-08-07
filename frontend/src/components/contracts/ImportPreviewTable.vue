<template>
  <div>
    <div class="table-responsive">
      <table class="table table-sm table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th style="width: 130px">Класс</th>
            <th>Файл / строка</th>
            <th>Организация</th>
            <th>Город / адрес</th>
            <th>Модель</th>
            <th>Серийный номер</th>
            <th>Замечания</th>
            <th v-if="editable" style="width: 170px">Решение</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>
              <span class="badge" :class="badgeClass(row.classification)">
                {{ classLabel(row.classification) }}
              </span>
            </td>
            <td class="small text-muted">{{ row.file }}<br>стр. {{ row.row_number }}</td>
            <td>{{ row.organization }}</td>
            <td>
              {{ row.city }}<br>
              <span class="small text-muted">{{ row.address }}<template v-if="row.room">, каб. {{ row.room }}</template></span>
            </td>
            <td>{{ row.model }}</td>
            <td><code>{{ row.serial }}</code></td>
            <td class="small">
              <div v-for="(err, i) in row.errors" :key="'e' + i" class="text-danger">{{ err.message }}</div>
              <div v-for="(warn, i) in row.warnings" :key="'w' + i" class="text-warning-emphasis">{{ warn.message }}</div>
              <div v-if="row.matched_device" class="text-muted">
                В базе: {{ row.matched_device.organization }}, {{ row.matched_device.address }}
              </div>
              <div v-if="row.apply_error" class="text-danger">{{ row.apply_error }}</div>
            </td>
            <td v-if="editable">
              <div v-if="isConflict(row.classification)" class="btn-group btn-group-sm w-100">
                <button
                  type="button"
                  class="btn"
                  :class="row.decision === 'apply' ? 'btn-success' : 'btn-outline-success'"
                  @click="$emit('decide', row.id, 'apply')"
                >Применить</button>
                <button
                  type="button"
                  class="btn"
                  :class="row.decision === 'skip' ? 'btn-secondary' : 'btn-outline-secondary'"
                  @click="$emit('decide', row.id, 'skip')"
                >Пропустить</button>
              </div>
              <span v-else-if="row.classification === 'error'" class="small text-muted">не применяется</span>
              <span v-else class="small text-muted">—</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="editable ? 8 : 7" class="text-center text-muted py-4">Строк нет</td>
          </tr>
        </tbody>
      </table>
    </div>

    <nav v-if="pageInfo.pages > 1" class="mt-3">
      <ul class="pagination pagination-sm mb-0 justify-content-center">
        <li class="page-item" :class="{ disabled: pageInfo.page <= 1 }">
          <button class="page-link" @click="$emit('page', pageInfo.page - 1)">Назад</button>
        </li>
        <li class="page-item disabled">
          <span class="page-link">{{ pageInfo.page }} из {{ pageInfo.pages }} ({{ pageInfo.total }})</span>
        </li>
        <li class="page-item" :class="{ disabled: pageInfo.page >= pageInfo.pages }">
          <button class="page-link" @click="$emit('page', pageInfo.page + 1)">Вперёд</button>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup>
import { CLASS_LABELS, CLASS_BADGES, CONFLICT_CLASSES } from './importConstants'

defineProps({
  rows: { type: Array, default: () => [] },
  pageInfo: { type: Object, default: () => ({ page: 1, pages: 1, total: 0 }) },
  editable: { type: Boolean, default: true }
})

defineEmits(['decide', 'page'])

const classLabel = (code) => CLASS_LABELS[code] || code
const badgeClass = (code) => CLASS_BADGES[code] || 'bg-secondary'
const isConflict = (code) => CONFLICT_CLASSES.includes(code)
</script>
