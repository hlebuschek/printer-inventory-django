<template>
  <div class="month-report-table">
    <!-- No data -->
    <div v-if="reports.length === 0" class="alert alert-info">
      Нет данных для отображения
    </div>

    <!-- Table -->
    <div v-else class="table-responsive">
      <table class="table table-sm table-striped table-hover table-bordered align-middle table-fixed">
        <colgroup>
          <col style="width: 60px;">  <!-- № -->
          <col style="width: 200px;"> <!-- Организация -->
          <col style="width: 150px;"> <!-- Филиал -->
          <col style="width: 120px;"> <!-- Город -->
          <col style="width: 250px;"> <!-- Адрес -->
          <col style="width: 220px;"> <!-- Модель -->
          <col style="width: 140px;"> <!-- Серийный номер -->
          <col style="width: 100px;"> <!-- Инв номер -->
          <!-- Счётчики -->
          <col style="width: 100px;"> <!-- A4 ч/б нач -->
          <col style="width: 100px;"> <!-- A4 ч/б кон -->
          <col style="width: 100px;"> <!-- A4 цв нач -->
          <col style="width: 100px;"> <!-- A4 цв кон -->
          <col style="width: 100px;"> <!-- A3 ч/б нач -->
          <col style="width: 100px;"> <!-- A3 ч/б кон -->
          <col style="width: 100px;"> <!-- A3 цв нач -->
          <col style="width: 100px;"> <!-- A3 цв кон -->
          <col style="width: 120px;"> <!-- Итого -->
          <col style="width: 80px;">  <!-- K1 -->
          <col style="width: 80px;">  <!-- K2 -->
        </colgroup>

        <thead class="table-light">
          <tr>
            <ColumnFilter
              column-key="num"
              label="№"
              placeholder="Номер..."
              :sort-state="getColumnSortState('num')"
              :is-active="isFilterActive('num')"
              :suggestions="[]"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="org"
              label="Организация"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('org')"
              :is-active="isFilterActive('org')"
              :suggestions="getSuggestions('org')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="branch"
              label="Филиал"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('branch')"
              :is-active="isFilterActive('branch')"
              :suggestions="getSuggestions('branch')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="city"
              label="Город"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('city')"
              :is-active="isFilterActive('city')"
              :suggestions="getSuggestions('city')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="address"
              label="Адрес"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('address')"
              :is-active="isFilterActive('address')"
              :suggestions="getSuggestions('address')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="model"
              label="Модель"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('model')"
              :is-active="isFilterActive('model')"
              :suggestions="getSuggestions('model')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="serial"
              label="Серийный №"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('serial')"
              :is-active="isFilterActive('serial')"
              :suggestions="getSuggestions('serial')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <ColumnFilter
              column-key="inv"
              label="Инв №"
              placeholder="Поиск..."
              :sort-state="getColumnSortState('inv')"
              :is-active="isFilterActive('inv')"
              :suggestions="getSuggestions('inv')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <th>A4 ч/б нач</th>
            <th>A4 ч/б кон</th>
            <th>A4 цв нач</th>
            <th>A4 цв кон</th>
            <th>A3 ч/б нач</th>
            <th>A3 ч/б кон</th>
            <th>A3 цв нач</th>
            <th>A3 цв кон</th>
            <th>Итого</th>
            <th>K1</th>
            <th>K2</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="(report, index) in reports"
            :key="report.id"
            :class="{ 'duplicate-row': report.duplicate_info }"
          >
            <td>{{ report.order_number }}</td>

            <!-- Серийный номер с подсветкой дублей -->
            <td>{{ report.organization }}</td>
            <td>{{ report.branch }}</td>
            <td>{{ report.city }}</td>
            <td>{{ report.address }}</td>
            <td>{{ report.equipment_model }}</td>

            <td
              :class="{ 'dup-serial': report.duplicate_info }"
              :title="report.duplicate_info ? `Дубль ${report.duplicate_info.position + 1} из ${report.duplicate_info.total_in_group}` : ''"
            >
              {{ report.serial_number }}
              <span v-if="report.duplicate_info" class="badge bg-success dup-position">
                {{ report.duplicate_info.position + 1 }}/{{ report.duplicate_info.total_in_group }}
              </span>
            </td>

            <td>{{ report.inventory_number }}</td>

            <!-- Счётчики - inline редактирование -->
            <CounterCell
              :report-id="report.id"
              field="a4_bw_start"
              :value="report.a4_bw_start"
              :editable="isEditable && permissions.edit_counters_start"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a4_bw_end"
              :value="report.a4_bw_end"
              :editable="isEditable && permissions.edit_counters_end"
              :is-manual="report.a4_bw_end_manual"
              :auto-value="report.a4_bw_end_auto"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a4_color_start"
              :value="report.a4_color_start"
              :editable="isEditable && permissions.edit_counters_start"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a4_color_end"
              :value="report.a4_color_end"
              :editable="isEditable && permissions.edit_counters_end"
              :is-manual="report.a4_color_end_manual"
              :auto-value="report.a4_color_end_auto"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a3_bw_start"
              :value="report.a3_bw_start"
              :editable="isEditable && permissions.edit_counters_start"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a3_bw_end"
              :value="report.a3_bw_end"
              :editable="isEditable && permissions.edit_counters_end"
              :is-manual="report.a3_bw_end_manual"
              :auto-value="report.a3_bw_end_auto"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a3_color_start"
              :value="report.a3_color_start"
              :editable="isEditable && permissions.edit_counters_start"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <CounterCell
              :report-id="report.id"
              field="a3_color_end"
              :value="report.a3_color_end"
              :editable="isEditable && permissions.edit_counters_end"
              :is-manual="report.a3_color_end_manual"
              :auto-value="report.a3_color_end_auto"
              :duplicate-info="report.duplicate_info"
              @saved="$emit('saved')"
            />

            <td class="fw-bold">{{ report.total_prints }}</td>
            <td>{{ report.k1.toFixed(1) }}%</td>
            <td>{{ report.k2.toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ColumnFilter from '../contracts/ColumnFilter.vue'
import CounterCell from './CounterCell.vue'

const props = defineProps({
  reports: {
    type: Array,
    required: true
  },
  choices: {
    type: Object,
    default: () => ({})
  },
  permissions: {
    type: Object,
    default: () => ({})
  },
  isEditable: {
    type: Boolean,
    default: false
  },
  currentSort: {
    type: Object,
    default: () => ({ column: null, descending: false })
  },
  activeFilters: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['filter', 'sort', 'clearFilter', 'saved'])

function getColumnSortState(columnKey) {
  if (!props.currentSort || props.currentSort.column !== columnKey) {
    return null
  }
  return props.currentSort.descending ? 'desc' : 'asc'
}

function isFilterActive(columnKey) {
  return props.activeFilters && props.activeFilters[columnKey] === true
}

function getSuggestions(columnKey) {
  const values = props.choices[columnKey] || []
  return values.map(v => ({ value: v, label: v }))
}

function handleFilter(columnKey, value, isMultiple = false) {
  emit('filter', columnKey, value, isMultiple)
}

function handleSort(columnKey, descending) {
  emit('sort', columnKey, descending)
}

function handleClearFilter(columnKey) {
  emit('clearFilter', columnKey)
}
</script>

<style scoped>
.table-fixed {
  table-layout: fixed;
  min-width: 100%;
}

.table-fixed th,
.table-fixed td {
  vertical-align: middle;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: normal;
}

/* Дублирующиеся серийники - зеленая подсветка */
td.dup-serial {
  background: linear-gradient(135deg, #d1e7dd 0%, #a3d9a4 100%) !important;
  border-left: 4px solid #198754;
  position: relative;
}

td.dup-serial:hover {
  background: linear-gradient(135deg, #a3d9a4 0%, #75c181 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(25, 135, 84, 0.2);
  transition: all 0.2s ease;
}

/* Позиция в группе */
.dup-position {
  font-size: 0.6rem;
  font-weight: 600;
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
  margin-left: 0.25rem;
}

.duplicate-row {
  background-color: #f8f9fa;
}
</style>
