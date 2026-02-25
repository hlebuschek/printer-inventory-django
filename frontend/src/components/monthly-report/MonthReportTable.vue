<template>
  <div class="month-report-table">
    <!-- Device Info Modal -->
    <DeviceInfoModal ref="deviceModalRef" />

    <!-- No data -->
    <div v-if="reports.length === 0" class="alert alert-info">
      Нет данных для отображения
    </div>

    <!-- Table -->
    <div v-if="reports.length > 0" ref="tableWrapperRef" class="table-wrapper">
      <div ref="tableContainerRef" class="table-responsive">
        <table ref="tableRef" class="table table-sm table-striped table-hover table-bordered align-middle table-fixed">
        <colgroup>
          <col style="width: 70px;">  <!-- № -->
          <col v-show="isVisible('org')" class="cg-org" style="width: 220px;">
          <col v-show="isVisible('branch')" class="cg-branch" style="width: 160px;">
          <col v-show="isVisible('city')" class="cg-city" style="width: 160px;">
          <col v-show="isVisible('address')" class="cg-address" style="width: 280px;">
          <col v-show="isVisible('model')" class="cg-model" style="width: 240px;">
          <col v-show="isVisible('serial')" class="cg-serial" style="width: 250px;">
          <col v-show="isVisible('inv')" class="cg-inv" style="width: 140px;">
          <!-- Счётчики -->
          <col v-show="isVisible('a4bw_s')" class="cg-a4bw_s" style="width: 120px;">
          <col v-show="isVisible('a4bw_e')" class="cg-a4bw_e" style="width: 120px;">
          <col v-show="isVisible('a4c_s')" class="cg-a4c_s" style="width: 120px;">
          <col v-show="isVisible('a4c_e')" class="cg-a4c_e" style="width: 120px;">
          <col v-show="isVisible('a3bw_s')" class="cg-a3bw_s" style="width: 120px;">
          <col v-show="isVisible('a3bw_e')" class="cg-a3bw_e" style="width: 120px;">
          <col v-show="isVisible('a3c_s')" class="cg-a3c_s" style="width: 120px;">
          <col v-show="isVisible('a3c_e')" class="cg-a3c_e" style="width: 120px;">
          <col v-show="isVisible('total')" class="cg-total" style="width: 150px;">
          <col v-show="isVisible('k1')" class="cg-K1" style="width: 120px;">
          <col v-show="isVisible('k2')" class="cg-K2" style="width: 120px;">
        </colgroup>

        <thead ref="theadRef" class="table-light">
          <!-- Строка с фильтрами/заголовками -->
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
              v-show="isVisible('org')"
              class="th-org"
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
              v-show="isVisible('branch')"
              class="th-branch"
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
              v-show="isVisible('city')"
              class="th-city"
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
              v-show="isVisible('address')"
              class="th-address"
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
              v-show="isVisible('model')"
              class="th-model"
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
              v-show="isVisible('serial')"
              class="th-serial"
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
              v-show="isVisible('inv')"
              class="th-inv"
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

            <th v-show="isVisible('a4bw_s')" class="th-a4bw_s">A4 ч/б нач</th>
            <th v-show="isVisible('a4bw_e')" class="th-a4bw_e">A4 ч/б кон</th>
            <th v-show="isVisible('a4c_s')" class="th-a4c_s">A4 цв нач</th>
            <th v-show="isVisible('a4c_e')" class="th-a4c_e">A4 цв кон</th>
            <th v-show="isVisible('a3bw_s')" class="th-a3bw_s">A3 ч/б нач</th>
            <th v-show="isVisible('a3bw_e')" class="th-a3bw_e">A3 ч/б кон</th>
            <th v-show="isVisible('a3c_s')" class="th-a3c_s">A3 цв нач</th>
            <th v-show="isVisible('a3c_e')" class="th-a3c_e">A3 цв кон</th>

            <ColumnFilter
              v-show="isVisible('total')"
              class="th-total"
              column-key="total"
              label="Итого"
              placeholder=""
              :sort-state="getColumnSortState('total')"
              :is-active="isFilterActive('total')"
              :suggestions="getSuggestions('total')"
              @filter="handleFilter"
              @sort="handleSort"
              @clear="handleClearFilter"
            />

            <th v-show="isVisible('k1')">K1</th>
            <th v-show="isVisible('k2')">K2</th>
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
            <td v-show="isVisible('org')">{{ report.organization }}</td>
            <td v-show="isVisible('branch')">{{ report.branch }}</td>
            <td v-show="isVisible('city')">{{ report.city }}</td>
            <td v-show="isVisible('address')">{{ report.address }}</td>
            <td v-show="isVisible('model')">{{ report.equipment_model }}</td>

            <td
              v-show="isVisible('serial')"
              :class="{ 'dup-serial': report.duplicate_info }"
            >
              <div class="d-flex align-items-center gap-2">
                <span class="text-nowrap">{{ report.serial_number }}</span>

                <!-- Индикатор позиции в группе дублей -->
                <span
                  v-if="report.duplicate_info"
                  class="badge bg-success dup-position text-white"
                  :title="`Позиция в группе дублей: ${report.duplicate_info.position + 1} из ${report.duplicate_info.total_in_group}`"
                >
                  {{ report.duplicate_info.position === 0 ? 'A4' : 'A3' }}
                </span>

                <!-- Кнопка истории изменений -->
                <a
                  :href="`/monthly-report/history/${report.id}/`"
                  class="btn btn-outline-secondary btn-sm py-0 px-1"
                  title="История изменений"
                  @click.stop
                >
                  📝
                </a>

                <!-- Бейджи IP·AUTO / IP·AUTO·РУЧН -->
                <span
                  v-if="hasAutoValues(report)"
                  class="badge rounded-pill device-info"
                  :class="{
                    'with-manual-fields': hasManualFields(report),
                    'text-bg-warning': isPollStale(report),
                    'bg-light border text-muted': !isPollStale(report)
                  }"
                  :title="getPollStatusTitle(report)"
                  role="button"
                  @click="showDeviceInfo(report)"
                >
                  {{ hasManualFields(report) ? 'IP·AUTO·РУЧН' : 'IP·AUTO' }}
                </span>
              </div>
            </td>

            <td v-show="isVisible('inv')">{{ report.inventory_number }}</td>

            <!-- Счётчики - inline редактирование -->
            <td v-show="isVisible('a4bw_s')" class="text-end col-a4bw_s">
              <CounterCell
                :report-id="report.id"
                field="a4_bw_start"
                :value="report.a4_bw_start"
                :editable="isEditable && permissions.edit_counters_start"
                :allowed="report.ui_allow_a4_bw_start !== false"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a4bw_e')" class="text-end col-a4bw_e">
              <CounterCell
                :report-id="report.id"
                field="a4_bw_end"
                :value="report.a4_bw_end"
                :editable="isEditable && permissions.edit_counters_end"
                :allowed="report.ui_allow_a4_bw_end !== false"
                :is-manual="report.a4_bw_end_manual"
                :auto-value="report.a4_bw_end_auto"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a4c_s')" class="text-end col-a4c_s">
              <CounterCell
                :report-id="report.id"
                field="a4_color_start"
                :value="report.a4_color_start"
                :editable="isEditable && permissions.edit_counters_start"
                :allowed="report.ui_allow_a4_color_start !== false"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a4c_e')" class="text-end col-a4c_e">
              <CounterCell
                :report-id="report.id"
                field="a4_color_end"
                :value="report.a4_color_end"
                :editable="isEditable && permissions.edit_counters_end"
                :allowed="report.ui_allow_a4_color_end !== false"
                :is-manual="report.a4_color_end_manual"
                :auto-value="report.a4_color_end_auto"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a3bw_s')" class="text-end col-a3bw_s">
              <CounterCell
                :report-id="report.id"
                field="a3_bw_start"
                :value="report.a3_bw_start"
                :editable="isEditable && permissions.edit_counters_start"
                :allowed="report.ui_allow_a3_bw_start !== false"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a3bw_e')" class="text-end col-a3bw_e">
              <CounterCell
                :report-id="report.id"
                field="a3_bw_end"
                :value="report.a3_bw_end"
                :editable="isEditable && permissions.edit_counters_end"
                :allowed="report.ui_allow_a3_bw_end !== false"
                :is-manual="report.a3_bw_end_manual"
                :auto-value="report.a3_bw_end_auto"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a3c_s')" class="text-end col-a3c_s">
              <CounterCell
                :report-id="report.id"
                field="a3_color_start"
                :value="report.a3_color_start"
                :editable="isEditable && permissions.edit_counters_start"
                :allowed="report.ui_allow_a3_color_start !== false"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <td v-show="isVisible('a3c_e')" class="text-end col-a3c_e">
              <CounterCell
                :report-id="report.id"
                field="a3_color_end"
                :value="report.a3_color_end"
                :editable="isEditable && permissions.edit_counters_end"
                :allowed="report.ui_allow_a3_color_end !== false"
                :is-manual="report.a3_color_end_manual"
                :auto-value="report.a3_color_end_auto"
                :duplicate-info="report.duplicate_info"
                @saved="handleCounterSaved"
              />
            </td>

            <!-- Total prints с подсветкой подозрительных/аномальных значений -->
            <td
              v-show="isVisible('total')"
              class="fw-bold total-cell"
              :class="{
                'high-value': report.total_prints > 10000,
                'anomaly-value': report.is_anomaly,
                'negative-value': report.total_prints < 0,
                'total-updated': report._wsUpdates && report._wsUpdates['total_prints']
              }"
              :title="getTotalTitle(report)"
            >
              {{ report.total_prints }}

              <!-- Подсказка расчета для дублей -->
              <div v-if="report.duplicate_info" class="total-meta">
                {{ report.duplicate_info.position === 0 ? '(только A4)' : '(только A3)' }}
              </div>
            </td>

            <td v-show="isVisible('k1')">{{ report.k1 ? report.k1.toFixed(1) : '' }}{{ report.k1 ? '%' : '' }}</td>
            <td v-show="isVisible('k2')">{{ report.k2 ? report.k2.toFixed(1) : '' }}{{ report.k2 ? '%' : '' }}</td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- Fixed header clone (показывается при прокрутке) -->
    <div v-if="reports.length > 0" ref="fixedHeaderRef" class="fixed-header-wrapper" :style="{ display: showFixedHeader ? 'block' : 'none' }">
      <!-- Будет заполнен клоном через JavaScript -->
    </div>

    <!-- Floating scrollbar -->
    <div v-if="reports.length > 0" ref="floatingScrollbarRef" class="floating-scrollbar" :class="{ 'show': showFloatingScrollbar }">
      <div ref="floatingScrollbarInnerRef" class="floating-scrollbar-inner">
        <div ref="floatingScrollbarContentRef" class="floating-scrollbar-content"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick } from 'vue'
import ColumnFilter from '../contracts/ColumnFilter.vue'
import CounterCell from './CounterCell.vue'
import DeviceInfoModal from './DeviceInfoModal.vue'

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
  },
  isVisible: {
    type: Function,
    required: true
  },
  year: {
    type: Number,
    required: true
  },
  month: {
    type: Number,
    required: true
  }
})

// Ref на таблицу и контейнеры
const tableRef = ref(null)
const tableWrapperRef = ref(null)
const tableContainerRef = ref(null)
const theadRef = ref(null)
const deviceModalRef = ref(null)

// Refs для floating scrollbar
const floatingScrollbarRef = ref(null)
const floatingScrollbarInnerRef = ref(null)
const floatingScrollbarContentRef = ref(null)
const showFloatingScrollbar = ref(false)

// Refs для fixed header
const fixedHeaderRef = ref(null)
const showFixedHeader = ref(false)

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
  return props.choices[columnKey] || []
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

function getTotalTitle(report) {
  const parts = []

  // Проверяем тип аномалии
  if (report.is_anomaly && report.anomaly_info) {
    const anomalyType = report.anomaly_info.anomaly_type

    if (anomalyType === 'both') {
      // И превышение, и сброс счётчика
      parts.push('⚠️ МНОЖЕСТВЕННАЯ АНОМАЛИЯ')
      parts.push(`❌ Отрицательное значение: ${report.total_prints}`)
      parts.push('🔄 Счётчик был сброшен')
      if (report.anomaly_info.has_history) {
        parts.push(`📊 Среднее за ${report.anomaly_info.months_count} мес.: ${report.anomaly_info.average}`)
      }
    } else if (anomalyType === 'negative') {
      // Отрицательное значение (сброс счётчика)
      parts.push('🔄 СБРОС СЧЁТЧИКА')
      parts.push(`❌ Отрицательное значение: ${report.total_prints}`)
      parts.push('Счётчик был сброшен во время месяца')
      if (report.anomaly_info.has_history) {
        parts.push(`📊 Обычное среднее: ${report.anomaly_info.average} отпечатков`)
      }
    } else if (anomalyType === 'excess' && report.anomaly_info.has_history) {
      // Превышение среднего
      parts.push('⚠️ ПРЕВЫШЕНИЕ СРЕДНЕГО')
      parts.push(`Текущее значение: ${report.total_prints} отпечатков`)
      parts.push(`Среднее за ${report.anomaly_info.months_count} мес.: ${report.anomaly_info.average} отпечатков`)
      parts.push(`Превышение: +${report.anomaly_info.difference} (${report.anomaly_info.percentage >= 0 ? '+' : ''}${report.anomaly_info.percentage}%)`)
    }
  }
  // Высокое значение (>10000) без аномалии
  else if (report.total_prints > 10000) {
    parts.push('📊 Высокое значение')
    parts.push(`Количество отпечатков: ${report.total_prints}`)

    // Если есть история, показываем среднее для контекста
    if (report.anomaly_info && report.anomaly_info.has_history) {
      parts.push(`Среднее за ${report.anomaly_info.months_count} мес.: ${report.anomaly_info.average}`)
    }
  }
  // Отрицательное значение (если не помечено как аномалия, но всё равно отрицательное)
  else if (report.total_prints < 0) {
    parts.push('🔄 СБРОС СЧЁТЧИКА')
    parts.push(`❌ Отрицательное значение: ${report.total_prints}`)
    parts.push('Счётчик был сброшен во время месяца')
  }

  return parts.join('\n')
}

function showDeviceInfo(report) {
  if (deviceModalRef.value) {
    deviceModalRef.value.show(report)
  }
}

/**
 * Handle counter cell saved event
 * Update report data without page reload
 */
function handleCounterSaved(eventData) {
  if (!eventData || !eventData.report) return

  // Find the report in the list
  const report = props.reports.find(r => r.id === eventData.reportId)
  if (!report) return

  // Update the field that was saved
  if (eventData.field && eventData.value !== undefined) {
    report[eventData.field] = eventData.value
  }

  // Update total_prints and other calculated fields from server response
  if (eventData.report.total_prints !== undefined) {
    report.total_prints = eventData.report.total_prints
  }

  // Update is_anomaly if provided
  if (eventData.report.is_anomaly !== undefined) {
    report.is_anomaly = eventData.report.is_anomaly
  }

  // Update anomaly_info if provided
  if (eventData.report.anomaly_info !== undefined) {
    report.anomaly_info = eventData.report.anomaly_info
  }

  // Emit saved event to parent
  emit('saved')
}

/**
 * Check if report has any auto values from inventory
 */
function hasAutoValues(report) {
  return !!(
    report.a4_bw_end_auto ||
    report.a4_color_end_auto ||
    report.a3_bw_end_auto ||
    report.a3_color_end_auto
  )
}

/**
 * Check if report has any manually edited fields
 */
function hasManualFields(report) {
  return !!(
    report.a4_bw_end_manual ||
    report.a4_color_end_manual ||
    report.a3_bw_end_manual ||
    report.a3_color_end_manual
  )
}

/**
 * Check if poll is stale (more than 7 days old)
 *
 * ВАЖНО: Желтая подсветка показывается ТОЛЬКО для текущего месяца!
 * Для закрытых месяцев подсветка отключена, т.к.:
 * - inventory_last_ok содержит дату последнего опроса ЗА ПЕРИОД месяца
 * - После закрытия месяца данные зафиксированы
 * - Сравнение с текущей датой теряет смысл
 */
function isPollStale(report) {
  if (!report.inventory_last_ok) return false

  try {
    const reportMonth = new Date(report.month)
    const reportEndDate = new Date(reportMonth.getFullYear(), reportMonth.getMonth() + 1, 0, 23, 59, 59)
    const now = new Date()

    // Для закрытых месяцев НЕ показываем желтую подсветку
    const isClosedMonth = reportEndDate < now

    if (isClosedMonth) {
      return false
    }

    // Для ТЕКУЩЕГО месяца проверяем актуальность
    const lastPoll = new Date(report.inventory_last_ok)
    const daysDiff = (now - lastPoll) / (1000 * 60 * 60 * 24)
    return daysDiff > 7
  } catch (e) {
    console.error("ERROR in isPollStale:", e)
    return false
  }
}

/**
 * Get poll status title for tooltip
 */
function getPollStatusTitle(report) {
  if (!report.inventory_last_ok) {
    return 'Устройство ещё не опрашивалось автоматически'
  }

  try {
    const lastPoll = new Date(report.inventory_last_ok)
    const reportMonth = new Date(report.month)
    const reportEndDate = new Date(reportMonth.getFullYear(), reportMonth.getMonth() + 1, 0, 23, 59, 59)
    const now = new Date()
    const isClosedMonth = reportEndDate < now

    const lastPollFormatted = lastPoll.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })

    // Для закрытых месяцев - просто показываем дату последнего опроса за период
    if (isClosedMonth) {
      return `Последний успешный опрос за период: ${lastPollFormatted}`
    }

    // Для текущего месяца - проверяем актуальность
    const daysDiff = Math.floor((now - lastPoll) / (1000 * 60 * 60 * 24))

    if (daysDiff > 7) {
      return `⚠️ Устаревшие данные! Последний успешный опрос: ${lastPollFormatted} (${daysDiff} дн. назад)`
    } else if (daysDiff === 0) {
      return `Последний успешный опрос: сегодня в ${lastPoll.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`
    } else if (daysDiff === 1) {
      return `Последний успешный опрос: вчера в ${lastPoll.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`
    } else {
      return `Последний успешный опрос: ${lastPollFormatted} (${daysDiff} дн. назад)`
    }
  } catch (e) {
    return 'Данные из автоопроса'
  }
}

/**
 * Setup floating scrollbar
 */
function setupFloatingScrollbar() {
  if (!tableWrapperRef.value || !floatingScrollbarInnerRef.value || !floatingScrollbarContentRef.value || !tableRef.value) {
    return
  }

  // Обновляем ширину контента floating scrollbar
  const updateWidth = () => {
    if (tableRef.value && floatingScrollbarContentRef.value) {
      const tableWidth = tableRef.value.scrollWidth
      floatingScrollbarContentRef.value.style.width = `${tableWidth}px`
    }
  }

  // Проверяем, нужен ли floating scrollbar
  const checkNeedScrollbar = () => {
    if (tableWrapperRef.value && tableRef.value) {
      const needsScroll = tableRef.value.scrollWidth > tableWrapperRef.value.clientWidth
      showFloatingScrollbar.value = needsScroll
      if (needsScroll) {
        updateWidth()
      }
    }
  }

  // Синхронизация скролла от wrapper к floating scrollbar
  const handleTableScroll = () => {
    if (tableWrapperRef.value && floatingScrollbarInnerRef.value) {
      floatingScrollbarInnerRef.value.scrollLeft = tableWrapperRef.value.scrollLeft
    }
  }

  // Синхронизация скролла от floating scrollbar к wrapper
  const handleFloatingScroll = () => {
    if (floatingScrollbarInnerRef.value && tableWrapperRef.value) {
      tableWrapperRef.value.scrollLeft = floatingScrollbarInnerRef.value.scrollLeft
    }
  }

  // Добавляем обработчики
  tableWrapperRef.value.addEventListener('scroll', handleTableScroll)
  floatingScrollbarInnerRef.value.addEventListener('scroll', handleFloatingScroll)
  window.addEventListener('resize', checkNeedScrollbar)

  // Первоначальная проверка
  nextTick(() => {
    checkNeedScrollbar()
  })

  // Возвращаем cleanup функции для onUnmounted
  return {
    cleanup: () => {
      if (tableWrapperRef.value) {
        tableWrapperRef.value.removeEventListener('scroll', handleTableScroll)
      }
      if (floatingScrollbarInnerRef.value) {
        floatingScrollbarInnerRef.value.removeEventListener('scroll', handleFloatingScroll)
      }
      window.removeEventListener('resize', checkNeedScrollbar)
    }
  }
}

/**
 * Setup fixed header (клонированный thead для фиксации при scroll)
 */
function setupFixedHeader() {
  if (!theadRef.value || !fixedHeaderRef.value || !tableWrapperRef.value || !tableRef.value) {
    return
  }

  const NAVBAR_HEIGHT = 56 // Высота navbar

  // Создаём клон thead
  const cloneHeader = () => {
    if (!theadRef.value || !fixedHeaderRef.value || !tableRef.value) return

    // Очищаем предыдущий клон
    fixedHeaderRef.value.innerHTML = ''

    // Создаём таблицу-обёртку для клона
    const tableClone = document.createElement('table')
    tableClone.className = tableRef.value.className
    tableClone.style.tableLayout = 'fixed'
    tableClone.style.width = `${tableRef.value.offsetWidth}px`
    tableClone.style.marginBottom = '0'

    // Клонируем colgroup для сохранения ширины колонок
    if (tableRef.value.querySelector('colgroup')) {
      const colgroupClone = tableRef.value.querySelector('colgroup').cloneNode(true)
      tableClone.appendChild(colgroupClone)
    }

    // Клонируем thead
    const theadClone = theadRef.value.cloneNode(true)

    // Копируем точные ширины из оригинальных th
    const originalThs = theadRef.value.querySelectorAll('th')
    const clonedThs = theadClone.querySelectorAll('th')

    originalThs.forEach((th, index) => {
      if (clonedThs[index]) {
        const width = th.getBoundingClientRect().width
        clonedThs[index].style.width = `${width}px`
        clonedThs[index].style.minWidth = `${width}px`
        clonedThs[index].style.maxWidth = `${width}px`
      }
    })

    tableClone.appendChild(theadClone)
    fixedHeaderRef.value.appendChild(tableClone)
  }

  // Проверяем нужно ли показывать fixed header
  const checkFixedHeaderVisibility = () => {
    if (!theadRef.value) return

    const theadRect = theadRef.value.getBoundingClientRect()
    const shouldShow = theadRect.top < NAVBAR_HEIGHT

    if (shouldShow !== showFixedHeader.value) {
      showFixedHeader.value = shouldShow
      if (shouldShow) {
        cloneHeader()
        // Сразу синхронизируем позицию
        nextTick(() => {
          syncHorizontalScroll()
        })
      }
    }
  }

  // Синхронизация горизонтального скролла и позиции
  const syncHorizontalScroll = () => {
    if (!tableWrapperRef.value || !fixedHeaderRef.value) return

    const wrapperRect = tableWrapperRef.value.getBoundingClientRect()
    const table = fixedHeaderRef.value.querySelector('table')

    if (table) {
      // Устанавливаем left чтобы совпал с wrapper
      fixedHeaderRef.value.style.left = `${wrapperRect.left}px`
      fixedHeaderRef.value.style.right = 'auto'
      fixedHeaderRef.value.style.width = `${wrapperRect.width}px`

      // Сдвигаем таблицу на величину горизонтального скролла
      table.style.transform = `translateX(-${tableWrapperRef.value.scrollLeft}px)`
    }
  }

  // Обработчик scroll страницы
  const handleScroll = () => {
    checkFixedHeaderVisibility()
    syncHorizontalScroll()
  }

  // Обработчик scroll wrapper
  const handleWrapperScroll = () => {
    syncHorizontalScroll()
  }

  // Обработчик resize - пересоздаём клон и синхронизируем позицию
  const handleResize = () => {
    if (showFixedHeader.value) {
      cloneHeader()
      nextTick(() => {
        syncHorizontalScroll()
      })
    }
  }

  // Добавляем обработчики
  window.addEventListener('scroll', handleScroll)
  tableWrapperRef.value.addEventListener('scroll', handleWrapperScroll)
  window.addEventListener('resize', handleResize)

  // Первоначальная проверка
  nextTick(() => {
    checkFixedHeaderVisibility()
  })

  return {
    cleanup: () => {
      window.removeEventListener('scroll', handleScroll)
      if (tableWrapperRef.value) {
        tableWrapperRef.value.removeEventListener('scroll', handleWrapperScroll)
      }
      window.removeEventListener('resize', handleResize)
    }
  }
}

// Store cleanup functions
let floatingScrollbarCleanup = null
let fixedHeaderCleanup = null

onMounted(() => {
  const floatingResult = setupFloatingScrollbar()
  if (floatingResult) {
    floatingScrollbarCleanup = floatingResult.cleanup
  }

  const fixedHeaderResult = setupFixedHeader()
  if (fixedHeaderResult) {
    fixedHeaderCleanup = fixedHeaderResult.cleanup
  }
})

onUnmounted(() => {
  // Cleanup floating scrollbar
  if (floatingScrollbarCleanup) {
    floatingScrollbarCleanup()
  }

  // Cleanup fixed header
  if (fixedHeaderCleanup) {
    fixedHeaderCleanup()
  }
})
</script>

<style scoped>
/* =========================
   STICKY HEADER - работает при прокрутке СТРАНИЦЫ
   ========================= */
.table-wrapper {
  position: relative;
  width: 100%;
  overflow-x: auto; /* Горизонтальный скролл только таблицы */
  /* overflow-y НЕ указываем - пусть будет visible по умолчанию для sticky */
}

.table-responsive {
  overflow: visible;
  margin-bottom: 1rem;
}

.table-fixed {
  table-layout: fixed;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

/* Оригинальный thead - обычный, без sticky
   Fixed header будет управляться через JavaScript */
.table-fixed thead {
  /* position: sticky убран - используем JavaScript решение */
}

.table-fixed thead th {
  background-color: #f8f9fa !important;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  border-bottom: 2px solid #dee2e6;
}

/* Fixed header wrapper (клонированный thead) */
.fixed-header-wrapper {
  position: fixed;
  top: 56px; /* Под navbar */
  left: 0;
  right: 0;
  z-index: 10;
  overflow: hidden; /* Скрываем горизонтальный скролл клона */
  background-color: transparent;
  pointer-events: none; /* Клик проходит сквозь wrapper */
}

.fixed-header-wrapper table {
  pointer-events: auto; /* Но на таблице клик работает */
}

.table-fixed th,
.table-fixed td {
  vertical-align: middle;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: normal;
}

/* =========================
   ДУБЛИРУЮЩИЕСЯ СЕРИЙНИКИ
   ========================= */
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

/* =========================
   ВЫСОКИЕ ЗНАЧЕНИЯ (>10000)
   ========================= */
.high-value {
  background: linear-gradient(135deg, #ffe6e6 0%, #ffcccc 100%) !important;
  border-left: 3px solid #dc3545;
  font-weight: 600;
  color: #721c24;
}

.high-value:hover {
  background: linear-gradient(135deg, #ffcccc 0%, #ffb3b3 100%) !important;
  box-shadow: 0 2px 4px rgba(220, 53, 69, 0.2);
  transition: all 0.2s ease;
}

/* =========================
   АНОМАЛЬНЫЕ ЗНАЧЕНИЯ (историческое среднее + 2000)
   ========================= */
.anomaly-value {
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%) !important;
  border-left: 3px solid #ffc107;
  font-weight: 600;
  color: #856404;
}

.anomaly-value:hover {
  background: linear-gradient(135deg, #fff3cc 0%, #ffeb99 100%) !important;
  box-shadow: 0 2px 4px rgba(255, 193, 7, 0.2);
  transition: all 0.2s ease;
}

/* Если оба условия выполнены - приоритет аномальным значениям */
.total-cell.high-value.anomaly-value {
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%) !important;
  border-left: 3px solid #ffc107 !important;
  color: #856404;
}

/* Отрицательные значения (красная подсветка) */
.total-cell.negative-value {
  background: linear-gradient(135deg, #f8d7da 0%, #ffe6e8 100%);
  border-left: 3px solid #dc3545;
  color: #842029;
  font-weight: 700;
}

.total-cell.negative-value:hover {
  background: linear-gradient(135deg, #f5c2c7 0%, #f8d7da 100%) !important;
  box-shadow: 0 2px 4px rgba(220, 53, 69, 0.3);
  transition: all 0.2s ease;
}

/* =========================
   РУЧНОЕ РЕДАКТИРОВАНИЕ
   ========================= */
.manual-edited {
  position: relative;
  background-color: #fff3cd !important;
  border-left: 3px solid #ffc107 !important;
}

.became-manual {
  animation: becameManual 2s ease-out;
}

@keyframes becameManual {
  0% {
    background-color: #d1ecf1;
    border-left-color: #0dcaf0;
    transform: scale(1);
  }
  30% {
    background-color: #ffeaa7;
    border-left-color: #fdcb6e;
    transform: scale(1.02);
  }
  100% {
    background-color: #fff3cd;
    border-left-color: #ffc107;
    transform: scale(1);
  }
}

/* =========================
   АНИМАЦИИ ОБНОВЛЕНИЯ
   ========================= */
.total-updated {
  animation: total-updated 1.5s ease-out;
  font-weight: bold;
}

@keyframes total-updated {
  0% { background: #fff3cd; color: #856404; transform: scale(1); }
  50% { background: #ffc107; color: #212529; transform: scale(1.05); }
  100% { background: transparent; color: inherit; transform: scale(1); }
}

/* =========================
   CLICKABLE CELL
   ========================= */
.clickable-cell {
  cursor: pointer;
  position: relative;
  transition: background-color 0.2s ease;
}

.clickable-cell:hover {
  background-color: rgba(13, 110, 253, 0.05) !important;
}

.clickable-cell .info-icon {
  color: #0d6efd;
  font-size: 0.85rem;
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.clickable-cell:hover .info-icon {
  opacity: 1;
}

/* =========================
   TOTAL META (подсказки для дублей)
   ========================= */
.total-meta {
  font-size: 0.65rem;
  font-style: italic;
  opacity: 0.8;
  color: #6c757d;
  margin-top: 0.2rem;
}

/* =========================
   DEVICE INFO BADGES
   ========================= */
.device-info {
  font-size: 0.7rem;
  padding: 0.25rem 0.4rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.device-info:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

/* бейдж с ручными полями - мягкий градиент (всегда, независимо от устаревших данных) */
.device-info.with-manual-fields {
  background: linear-gradient(45deg, #e3f2fd, #fff3cd) !important;
  border: 1px solid #b0bec5 !important;
  color: #495057 !important;
}

/* бейдж с устаревшими данными автоопроса (> 7 дней) - только для IP·AUTO без РУЧН */
.device-info.text-bg-warning:not(.with-manual-fields) {
  background: #ffc107 !important;
  color: #000 !important;
  border: 1px solid #ff9800 !important;
  font-weight: 600 !important;
}

/* =========================
   АДАПТИВНОСТЬ
   ========================= */
@media (max-width: 768px) {
  .dup-position {
    font-size: 0.5rem;
    padding: 0.05rem 0.2rem;
  }

  .info-icon {
    display: none;
  }

  .total-meta {
    display: none;
  }

  .device-info {
    font-size: 0.6rem;
    padding: 0.2rem 0.3rem;
  }
}

/* =========================
   DARK THEME — подсветка ячейки «Итого»
   ========================= */
[data-bs-theme="dark"] .high-value {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.3) 0%, rgba(220, 53, 69, 0.2) 100%) !important;
  border-left: 3px solid #f1717e;
  color: #f1717e !important;
}

[data-bs-theme="dark"] .high-value:hover {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.4) 0%, rgba(220, 53, 69, 0.3) 100%) !important;
  box-shadow: 0 2px 4px rgba(220, 53, 69, 0.3);
}

[data-bs-theme="dark"] .anomaly-value {
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.25) 0%, rgba(255, 193, 7, 0.15) 100%) !important;
  border-left: 3px solid #ffc107;
  color: #ffd754 !important;
}

[data-bs-theme="dark"] .anomaly-value:hover {
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.35) 0%, rgba(255, 193, 7, 0.25) 100%) !important;
  box-shadow: 0 2px 4px rgba(255, 193, 7, 0.25);
}

[data-bs-theme="dark"] .total-cell.high-value.anomaly-value {
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.25) 0%, rgba(255, 193, 7, 0.15) 100%) !important;
  border-left: 3px solid #ffc107 !important;
  color: #ffd754 !important;
}

[data-bs-theme="dark"] .total-cell.negative-value {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.3) 0%, rgba(220, 53, 69, 0.2) 100%) !important;
  border-left: 3px solid #f1717e;
  color: #f1717e !important;
}

[data-bs-theme="dark"] .total-cell.negative-value:hover {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.4) 0%, rgba(220, 53, 69, 0.3) 100%) !important;
  box-shadow: 0 2px 4px rgba(220, 53, 69, 0.3);
}

/* =========================
   FLOATING SCROLLBAR
   ========================= */
.floating-scrollbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 17px;
  background: rgba(248, 249, 250, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  z-index: 1000;
  display: none;
  backdrop-filter: blur(3px);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.floating-scrollbar.show {
  display: block;
}

.floating-scrollbar-inner {
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.floating-scrollbar-content {
  height: 1px;
}

/* Улучшенный стиль скроллбара */
.floating-scrollbar-inner::-webkit-scrollbar {
  height: 14px;
}

.floating-scrollbar-inner::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
}

.floating-scrollbar-inner::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 7px;
  border: 2px solid rgba(248, 249, 250, 0.95);
}

.floating-scrollbar-inner::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.5);
}
</style>
