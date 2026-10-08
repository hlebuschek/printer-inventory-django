<template>
  <div>
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
      <div class="table-wrapper">
      <table ref="tableRef" class="table table-sm table-striped table-hover table-bordered align-middle table-fixed table-resizable">
        <colgroup>
          <col style="width: 70px;">
          <col
            v-for="col in orderedColumns"
            :key="col.key"
            :class="[columnMeta[col.key]?.colClass, { 'd-none': !col.visible, 'cg-dragging': dragHeaderKey === col.key }]"
            :style="{ width: columnMeta[col.key]?.width }"
          >
        </colgroup>

        <thead class="table-light">
          <tr>
            <th>№</th>
            <template v-for="col in orderedColumns" :key="col.key">
              <th
                v-if="col.key === 'actions'"
                class="text-center th-actions"
                data-col-key="actions"
              >Действия</th>
              <ColumnFilter
                v-else
                :class="[{
                  'd-none': !col.visible,
                  'text-center': columnMeta[col.key]?.center,
                  'th-dragging': dragHeaderKey === col.key,
                  'th-drop-left': dropMarker.key === col.key && dropMarker.side === 'left',
                  'th-drop-right': dropMarker.key === col.key && dropMarker.side === 'right'
                }]"
                :data-col-key="col.key"
                draggable="true"
                @dragstart="onHeaderDragStart(col, $event)"
                @dragover.prevent="onHeaderDragOver(col)"
                @drop.prevent="onHeaderDrop(col)"
                @dragend="onHeaderDragEnd"
                :th-class="columnMeta[col.key]?.thClass"
                :label="columnMeta[col.key]?.label || col.key"
                :column-key="colFilterKey(col.key)"
                :sortable="columnMeta[col.key]?.sortable !== false"
                :ops="columnMeta[col.key]?.ops !== false"
                :suggestions="colChoices(col.key)"
                :sort-state="getColumnSortState(colFilterKey(col.key))"
                :is-active="isFilterActive(colFilterKey(col.key))"
                :value="colFilterState(col.key).value || ''"
                :current-multi="colFilterState(col.key).multi || ''"
                :current-op="colFilterState(col.key).op || ''"
                @filter="handleFilter"
                @sort="handleSort"
                @clear="handleClearFilter"
              />
            </template>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="(device, index) in devices"
            :key="device.id"
            :class="{ editing: isEditing(device.id) }"
            :data-pk="device.id"
          >
            <td>{{ startIndex + index + 1 }}</td>

            <template v-for="col in orderedColumns" :key="col.key">
            <!-- Организация -->
            <td v-if="col.key === 'org'" :class="['col-org', { 'd-none': !col.visible }]" :data-org-id="device.organization_id">
              <SearchableSelect
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).organization_id"
                :options="organizationOptions"
                size="sm"
                fixed-dropdown
                placeholder="Организация"
              />
              <span v-else>{{ device.organization }}</span>
            </td>

            <!-- Город -->
            <td v-else-if="col.key === 'city'" :class="['col-city', { 'd-none': !col.visible }]" :data-city-id="device.city_id">
              <SearchableSelect
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).city_id"
                :options="cityOptions"
                size="sm"
                fixed-dropdown
                placeholder="Город"
              />
              <span v-else>{{ device.city }}</span>
            </td>

            <!-- Адрес -->
            <td v-else-if="col.key === 'address'" :class="['col-address addr', { 'd-none': !col.visible }]">
              <input
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).address"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.address }}</span>
            </td>

            <!-- Адрес (GLPI) -->
            <td v-else-if="col.key === 'glpi_location'" :class="['col-glpi-location addr', { 'd-none': !col.visible }]">
              <span
                v-if="device.glpi_location"
                :class="{ 'text-warning-emphasis': isLocationMismatch(device) }"
                :title="isLocationMismatch(device) ? 'Город не совпадает с адресом в GLPI' : ''"
              >
                <i v-if="isLocationMismatch(device)" class="bi bi-exclamation-triangle me-1"></i>{{ device.glpi_location }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- Кабинет -->
            <td v-else-if="col.key === 'room'" :class="['col-room', { 'd-none': !col.visible }]">
              <input
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).room_number"
                type="text"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.room_number }}</span>
            </td>

            <!-- Производитель -->
            <td v-else-if="col.key === 'mfr'" :class="['col-mfr', { 'd-none': !col.visible }]" :data-mfr-id="device.manufacturer_id">
              <SearchableSelect
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).manufacturer_id"
                :options="manufacturerOptions"
                size="sm"
                fixed-dropdown
                placeholder="Производитель"
                @update:model-value="loadModelsForManufacturer(device.id)"
              />
              <span v-else>{{ device.manufacturer }}</span>
            </td>

            <!-- Модель -->
            <td v-else-if="col.key === 'model'" :class="['col-model', { 'd-none': !col.visible }]" :data-model-id="device.model_id">
              <SearchableSelect
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).model_id"
                :options="getModelOptions(device.id)"
                size="sm"
                fixed-dropdown
                placeholder="Модель"
                :disabled="!getEditForm(device.id).manufacturer_id"
              />
              <span v-else>{{ device.model }}</span>
            </td>

            <!-- Серийный номер -->
            <td v-else-if="col.key === 'serial'" :class="['col-serial', { 'd-none': !col.visible }]">
              <input
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).serial_number"
                type="text"
                class="form-control form-control-sm"
              />
              <template v-else>
                {{ device.serial_number }}
                <br v-if="device.printer_id">
                <button
                  v-if="device.printer_id"
                  class="btn btn-link btn-sm p-0"
                  type="button"
                  @click="openPrinterModal(device.printer_id)"
                >
                  ↗ опрос
                </button>
              </template>
            </td>

            <!-- Месяц обслуживания -->
            <td v-else-if="col.key === 'service_month'" :class="['col-service-month', { 'd-none': !col.visible }]" :data-service-month="device.service_start_month_iso || ''">
              <input
                v-if="isEditing(device.id)"
                v-model="getEditForm(device.id).service_start_month"
                type="month"
                class="form-control form-control-sm"
              />
              <span v-else>{{ device.service_start_month || '—' }}</span>
            </td>

            <!-- Счётчик при приёмке -->
            <td
              v-else-if="col.key === 'initial_counter'"
              :class="['col-initial-counter', {
                'd-none': !col.visible,
                'pdf-drop-active': pdfDropTargetId === device.id
              }]"
              @dragover="onPdfDragOver(device, $event)"
              @dragleave="pdfDropTargetId = null"
              @drop="onPdfDrop(device, $event)"
            >
              <template v-if="isEditing(device.id)">
                <input
                  v-model="getEditForm(device.id).initial_counter"
                  type="number"
                  min="0"
                  class="form-control form-control-sm mb-1"
                  placeholder="Счётчик"
                />
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  class="form-control form-control-sm"
                  title="PDF конфигурационной страницы (можно несколько)"
                  @change="onPdfSelected(device.id, $event)"
                />
                <div v-for="doc in device.acceptance_docs" :key="doc.id" class="d-flex align-items-center gap-1 mt-1 small">
                  <i class="bi bi-file-earmark-pdf text-danger"></i>
                  <span class="text-truncate" :title="doc.name">{{ doc.name }}</span>
                  <button
                    class="btn btn-link btn-sm p-0 text-danger"
                    type="button"
                    title="Удалить файл"
                    @click="deleteAcceptanceDoc(device, doc)"
                  >
                    <i class="bi bi-x-circle"></i>
                  </button>
                </div>
              </template>
              <template v-else>
                <span v-if="device.initial_counter !== null && device.initial_counter !== undefined">
                  {{ device.initial_counter.toLocaleString('ru-RU') }}
                </span>
                <span v-else class="text-muted">—</span>
                <div v-for="doc in device.acceptance_docs" :key="doc.id" class="small">
                  <a
                    :href="`/contracts/api/acceptance-docs/${doc.id}/`"
                    target="_blank"
                    class="text-decoration-none"
                    :title="`${doc.name} — ${formatDocDate(doc.uploaded_at)}`"
                  >
                    <i class="bi bi-file-earmark-pdf text-danger"></i> PDF
                  </a>
                </div>
              </template>
            </td>

            <!-- Статус -->
            <td v-else-if="col.key === 'status'" :class="['col-status', { 'd-none': !col.visible }]" :data-status-id="device.status_id">
              <SearchableSelect
                v-if="isEditing(device.id)"
                v-model="getEditForm(device.id).status_id"
                :options="statusOptions"
                size="sm"
                fixed-dropdown
                placeholder="Статус"
              />
              <span
                v-else-if="device.status"
                class="badge rounded-pill"
                :style="{ backgroundColor: device.status_color, color: getContrastColor(device.status_color) }"
              >
                {{ device.status }}
              </span>
              <span v-else>—</span>
            </td>

            <!-- Подрядчик -->
            <td v-else-if="col.key === 'provider'" :class="['col-provider', { 'd-none': !col.visible }]" :data-provider-id="device.service_provider_id">
              <SearchableSelect
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).service_provider_id"
                :options="providerOptions"
                size="sm"
                fixed-dropdown
                placeholder="—"
              />
              <span v-else-if="device.service_provider">{{ device.service_provider }}</span>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- Комментарий -->
            <td v-else-if="col.key === 'comment'" :class="['col-comment comment', { 'd-none': !col.visible }]">
              <textarea
                v-if="isFullEditing(device.id)"
                v-model="getEditForm(device.id).comment"
                class="form-control form-control-sm"
                rows="2"
              ></textarea>
              <span v-else>{{ device.comment }}</span>
            </td>

            <!-- Автор заявки Okdesk -->
            <td v-else-if="col.key === 'okdesk_author'" :class="['col-okdesk-author', { 'd-none': !col.visible }]">
              <span v-if="device.okdesk_author_name">{{ device.okdesk_author_name }}</span>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- Активные заявки Okdesk -->
            <td v-else-if="col.key === 'okdesk_active'" :class="['text-center', { 'd-none': !col.visible }]">
              <i v-if="device.has_active_issues" class="bi bi-check-circle-fill text-warning" title="Есть активные заявки"></i>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- Просроченные заявки Okdesk -->
            <td v-else-if="col.key === 'okdesk_overdue'" :class="['text-center', { 'd-none': !col.visible }]">
              <i v-if="device.has_overdue_issues" class="bi bi-exclamation-triangle-fill text-danger" title="Есть просроченные заявки"></i>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- GLPI -->
            <td v-else-if="col.key === 'glpi'" :class="['col-glpi text-center', { 'd-none': !col.visible }]">
              <div v-if="device.glpi_status" class="d-flex flex-column gap-1 align-items-center">
                <span
                  class="badge"
                  :class="getGLPIStatusClass(device.glpi_status)"
                  :title="device.glpi_status_display"
                >
                  {{ device.glpi_status_display }}
                  <span v-if="device.glpi_count > 1" class="ms-1">({{ device.glpi_count }})</span>
                </span>
                <small v-if="device.glpi_checked_at" class="text-muted" style="font-size: 0.7rem;">
                  {{ formatGLPIDate(device.glpi_checked_at) }}
                </small>
                <button
                  class="btn btn-outline-primary btn-sm"
                  style="font-size: 0.7rem; padding: 0.1rem 0.3rem;"
                  :disabled="isCheckingGLPI(device.id)"
                  @click="checkInGLPI(device.id)"
                >
                  <i class="bi bi-arrow-repeat" :class="{ 'spin': isCheckingGLPI(device.id) }"></i>
                  {{ isCheckingGLPI(device.id) ? 'Проверка...' : 'Проверить' }}
                </button>
              </div>
              <div v-else class="d-flex flex-column gap-1 align-items-center">
                <span class="badge bg-secondary">Не проверялось</span>
                <button
                  class="btn btn-outline-primary btn-sm"
                  style="font-size: 0.7rem; padding: 0.1rem 0.3rem;"
                  :disabled="isCheckingGLPI(device.id)"
                  @click="checkInGLPI(device.id)"
                >
                  <i class="bi bi-cloud-check" :class="{ 'spin': isCheckingGLPI(device.id) }"></i>
                  {{ isCheckingGLPI(device.id) ? 'Проверка...' : 'Проверить' }}
                </button>
              </div>
            </td>

            <!-- Состояние в GLPI -->
            <td v-else-if="col.key === 'glpi_state'" :class="['col-glpi-state text-center', { 'd-none': !col.visible }]">
              <span v-if="device.glpi_state_name" class="text-muted" style="font-size: 0.875rem;">
                {{ device.glpi_state_name }}
              </span>
              <span v-else class="text-muted" style="font-size: 0.75rem;">—</span>
            </td>

            <!-- Действия -->
            <td v-else-if="col.key === 'actions'" class="col-actions">
              <div class="btn-group btn-group-sm action-group" role="group" aria-label="Действия">
                <!-- Edit button -->
                <button
                  v-if="canEditDevices && !isEditing(device.id)"
                  class="btn btn-outline-secondary btn-icon row-edit"
                  title="Редактировать"
                  aria-label="Редактировать"
                  @click="startEdit(device)"
                >
                  <i class="bi bi-pencil"></i>
                </button>

                <!-- Email button -->
                <a
                  v-if="!isEditing(device.id)"
                  :href="`/contracts/${device.id}/email/`"
                  class="btn btn-outline-info btn-icon"
                  title="Скачать письмо с информацией"
                  aria-label="Скачать письмо"
                >
                  <i class="bi bi-envelope"></i>
                </a>

                <!-- History button -->
                <button
                  v-if="permissions.view_entity_changes && !isEditing(device.id)"
                  class="btn btn-outline-primary btn-icon"
                  title="История изменений"
                  aria-label="История изменений"
                  @click="openChangeHistory(device.id)"
                >
                  <i class="bi bi-clock-history"></i>
                </button>

                <!-- Okdesk issues button -->
                <button
                  v-if="permissions.view_okdesk_issues && !isEditing(device.id)"
                  class="btn btn-outline-warning btn-icon"
                  title="Заявки Okdesk"
                  aria-label="Заявки Okdesk"
                  @click="openOkdeskIssues(device)"
                >
                  <i class="bi bi-ticket-detailed"></i>
                </button>

                <!-- Delete button -->
                <button
                  v-if="permissions.delete_contractdevice && !isEditing(device.id)"
                  class="btn btn-outline-danger btn-icon row-delete"
                  title="Удалить"
                  aria-label="Удалить"
                  @click="$emit('delete', device)"
                >
                  <i class="bi bi-trash"></i>
                </button>

                <!-- Save button (visible when editing) -->
                <button
                  v-if="canEditDevices && isEditing(device.id)"
                  class="btn btn-outline-success btn-icon row-save"
                  title="Сохранить"
                  aria-label="Сохранить"
                  :disabled="isSaving.has(device.id)"
                  @click="saveEdit(device.id)"
                >
                  <i class="bi bi-check2"></i>
                </button>

                <!-- Cancel button (visible when editing) -->
                <button
                  v-if="canEditDevices && isEditing(device.id)"
                  class="btn btn-outline-secondary btn-icon row-cancel"
                  title="Отмена"
                  aria-label="Отмена"
                  :disabled="isSaving.has(device.id)"
                  @click="cancelEdit(device.id)"
                >
                  <i class="bi bi-x"></i>
                </button>
              </div>
            </td>
            </template>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- Printer Modal -->
    <PrinterModal
      v-model:show="showPrinterModal"
      :printer-id="selectedPrinterId"
      :organizations="filterData.organizations"
      :permissions="permissions"
      @updated="handlePrinterUpdated"
    />

    <!-- Change History Modal -->
    <ChangeHistoryModal
      :show="showHistoryModal"
      :history-url="historyUrl"
      @close="showHistoryModal = false"
    />

    <!-- Okdesk Issues Modal -->
    <OkdeskIssuesModal
      :show="showIssuesModal"
      :device-id="issuesDeviceId"
      :device-serial="issuesDeviceSerial"
      :can-create="permissions.create_okdesk_issue && issuesOkdeskEnabled"
      :provider-notice="issuesProviderNotice"
      @close="showIssuesModal = false"
      @created="emit('issue-created', $event)"
    />

    <!-- Fixed Scrollbar -->
    <FixedScrollbar target-selector=".table-wrapper" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useToast } from '../../composables/useToast'
import { useColumnResize } from '../../composables/useColumnResize'
import ColumnFilter from './ColumnFilter.vue'
import PrinterModal from '../inventory/PrinterModal.vue'
import ChangeHistoryModal from '../common/ChangeHistoryModal.vue'
import OkdeskIssuesModal from './OkdeskIssuesModal.vue'
import FixedScrollbar from '../common/FixedScrollbar.vue'
import SearchableSelect from '../common/SearchableSelect.vue'

const tableRef = ref(null)

// Change history modal state
const showHistoryModal = ref(false)
const historyUrl = ref('')

// Okdesk issues modal state
const showIssuesModal = ref(false)
const issuesDeviceId = ref(null)
const issuesDeviceSerial = ref('')
const issuesOkdeskEnabled = ref(true)
const issuesProviderNotice = ref('')

const props = defineProps({
  devices: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  filterData: {
    type: Object,
    default: () => ({
      organizations: [],
      cities: [],
      manufacturers: [],
      statuses: [],
      providers: []
    })
  },
  columns: {
    type: Array,
    default: () => []
  },
  permissions: {
    type: Object,
    default: () => ({})
  },
  currentSort: {
    type: Object,
    default: () => ({ column: null, descending: false })
  },
  activeFilters: {
    type: Object,
    default: () => ({})
  },
  columnFilterState: {
    type: Object,
    default: () => ({})
  },
  startIndex: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['edit', 'delete', 'saved', 'filter', 'sort', 'clearFilter', 'issue-created', 'reorder'])

// Метаданные колонок: ширина, классы, подписи, особенности фильтрации
const columnMeta = {
  org: { width: '220px', colClass: 'cg-org', thClass: 'th-org', label: 'Организация' },
  city: { width: '160px', colClass: 'cg-city', thClass: 'th-city', label: 'Город' },
  address: { width: '280px', colClass: 'cg-address', thClass: 'th-address', label: 'Адрес' },
  glpi_location: { width: '280px', colClass: 'cg-glpi-location', thClass: 'th-glpi-location', label: 'Адрес (GLPI)' },
  room: { width: '130px', colClass: 'cg-room', thClass: 'th-room', label: '№ кабинета' },
  mfr: { width: '200px', colClass: 'cg-mfr', thClass: 'th-mfr', label: 'Производитель' },
  model: { width: '260px', colClass: 'cg-model', thClass: 'th-model', label: 'Модель оборудования' },
  serial: { width: '190px', colClass: 'cg-serial', thClass: 'th-serial', label: 'Серийный номер' },
  service_month: { width: '140px', colClass: 'cg-service_month', thClass: 'th-service_month', label: 'Месяц обслуживания', ops: false },
  initial_counter: {
    width: '160px', colClass: 'cg-initial-counter', thClass: 'th-initial-counter',
    label: 'Счётчик при приёмке', filterKey: 'acceptance', ops: false
  },
  status: { width: '220px', colClass: 'cg-status', thClass: 'th-status', label: 'Статус' },
  provider: { width: '150px', colClass: 'cg-provider', thClass: 'th-provider', label: 'Подрядчик' },
  comment: { width: '400px', colClass: 'cg-comment', thClass: 'th-comment', label: 'Комментарий' },
  okdesk_author: {
    width: '200px', colClass: 'cg-okdesk-author', thClass: 'th-okdesk-author',
    label: 'Автор заявки', sortable: false, ops: false
  },
  okdesk_active: {
    width: '80px', colClass: 'cg-okdesk-active', thClass: 'th-okdesk-active',
    label: 'Заявки', sortable: false, center: true, ops: false
  },
  okdesk_overdue: {
    width: '80px', colClass: 'cg-okdesk-overdue', thClass: 'th-okdesk-overdue',
    label: 'Просроч.', sortable: false, center: true, ops: false
  },
  glpi: {
    width: '180px', colClass: 'cg-glpi', thClass: 'th-glpi',
    label: 'GLPI', filterKey: 'glpi_status', choicesKey: 'glpi', sortable: false, center: true, ops: false
  },
  glpi_state: {
    width: '150px', colClass: 'cg-glpi-state', thClass: 'th-glpi-state',
    label: 'Состояние в GLPI', sortable: false, center: true, ops: false
  },
  actions: { width: '200px', colClass: 'cg-actions', label: 'Действия' }
}

const orderedColumns = computed(() =>
  props.columns.length
    ? props.columns
    : Object.keys(columnMeta).map(key => ({ key, visible: true }))
)

function colFilterKey(key) {
  return columnMeta[key]?.filterKey || key
}

function colChoices(key) {
  const choicesKey = columnMeta[key]?.choicesKey || colFilterKey(key)
  return props.filterData.choices?.[choicesKey] || []
}

function colFilterState(key) {
  return props.columnFilterState[colFilterKey(key)] || {}
}

// Перетаскивание колонок за заголовки
const dragHeaderKey = ref(null)
const dropMarker = reactive({ key: null, side: null })

function onHeaderDragStart(col, event) {
  dragHeaderKey.value = col.key
  event.dataTransfer.effectAllowed = 'move'
  // Firefox требует setData, иначе drag не стартует
  event.dataTransfer.setData('text/plain', col.key)
}

function onHeaderDragOver(col) {
  if (!dragHeaderKey.value || col.key === dragHeaderKey.value) {
    dropMarker.key = null
    dropMarker.side = null
    return
  }
  const from = orderedColumns.value.findIndex(c => c.key === dragHeaderKey.value)
  const to = orderedColumns.value.findIndex(c => c.key === col.key)
  dropMarker.key = col.key
  dropMarker.side = from < to ? 'right' : 'left'
}

function onHeaderDrop(col) {
  if (dragHeaderKey.value && col.key !== dragHeaderKey.value) {
    emit('reorder', dragHeaderKey.value, col.key)
  }
  onHeaderDragEnd()
}

function onHeaderDragEnd() {
  dragHeaderKey.value = null
  dropMarker.key = null
  dropMarker.side = null
}

const { showToast } = useToast()

// Initialize column resizing
const { initResize, cleanupResize } = useColumnResize(tableRef, 'contracts:columnWidths')

// Re-initialize resize handles after table re-renders (v-if destroys/recreates the DOM)
watch(() => props.loading, (newVal, oldVal) => {
  if (oldVal && !newVal) {
    nextTick(() => {
      cleanupResize()
      initResize()
    })
  }
})

// Multiple row editing support
const editingIds = ref(new Set())
const isSaving = ref(new Set())
const editForms = ref({})
const availableModelsMap = ref({})
const pdfFiles = ref({})

// Printer modal state
const showPrinterModal = ref(false)
const selectedPrinterId = ref(null)

// GLPI checking state
const checkingGLPI = ref(new Set())

// Полное редактирование или только поля приёмки (счётчик, PDF, статус, месяц)
const fullEdit = computed(() => !!props.permissions.change_contractdevice)
const canEditDevices = computed(() => fullEdit.value || !!props.permissions.manage_device_acceptance)

function isEditing(deviceId) {
  return editingIds.value.has(deviceId)
}

function isFullEditing(deviceId) {
  return isEditing(deviceId) && fullEdit.value
}

function getEditForm(deviceId) {
  return editForms.value[deviceId] || {}
}

function getAvailableModels(deviceId) {
  return availableModelsMap.value[deviceId] || []
}

const toOptions = (items) => (items || []).map(i => ({ value: i.id, label: i.name }))
const organizationOptions = computed(() => toOptions(props.filterData.organizations))
const cityOptions = computed(() => toOptions(props.filterData.cities))
const manufacturerOptions = computed(() => toOptions(props.filterData.manufacturers))
const statusOptions = computed(() => toOptions(props.filterData.statuses))
const providerOptions = computed(() => toOptions(props.filterData.providers))

function getModelOptions(deviceId) {
  return toOptions(getAvailableModels(deviceId))
}

function getColumnSortState(columnKey) {
  if (!props.currentSort || props.currentSort.column !== columnKey) {
    return null
  }
  return props.currentSort.descending ? 'desc' : 'asc'
}

function isFilterActive(columnKey) {
  return props.activeFilters && props.activeFilters[columnKey] === true
}

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function getContrastColor(hexColor) {
  if (!hexColor) return '#fff'
  
  let hex = hexColor.replace('#', '')
  if (hex.length === 3) {
    hex = hex.split('').map(c => c + c).join('')
  }
  if (hex.length !== 6) return '#fff'
  
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  
  return (r * 299 + g * 587 + b * 114) / 1000 > 140 ? '#000' : '#fff'
}

function handleFilter(columnKey, value, isMultiple = false, op = '') {
  emit('filter', columnKey, value, isMultiple, op)
}

function handleSort(columnKey, descending) {
  emit('sort', columnKey, descending)
}

function handleClearFilter(columnKey) {
  emit('clearFilter', columnKey)
}

function openPrinterModal(printerId) {
  selectedPrinterId.value = printerId
  showPrinterModal.value = true
}

function handlePrinterUpdated() {
  // Reload devices after printer is updated
  emit('saved')
}

function openChangeHistory(deviceId) {
  historyUrl.value = `/contracts/api/${deviceId}/history/`
  showHistoryModal.value = true
}

function openOkdeskIssues(device) {
  issuesDeviceId.value = device.id
  issuesDeviceSerial.value = device.serial_number || ''
  issuesOkdeskEnabled.value = device.okdesk_enabled !== false
  issuesProviderNotice.value = issuesOkdeskEnabled.value
    ? ''
    : `Устройство обслуживает «${device.service_provider}» — новые заявки подаются не через Okdesk. Ниже только история.`
  showIssuesModal.value = true
}

function startEdit(device) {
  // Add device ID to editing set
  editingIds.value.add(device.id)

  // Create form for this device
  editForms.value[device.id] = {
    organization_id: device.organization_id,
    city_id: device.city_id,
    address: device.address,
    room_number: device.room_number,
    manufacturer_id: '',
    model_id: device.model_id,
    serial_number: device.serial_number,
    status_id: device.status_id,
    service_provider_id: device.service_provider_id || '',
    service_start_month: device.service_start_month_iso || '',
    initial_counter: device.initial_counter ?? '',
    comment: device.comment || ''
  }
  pdfFiles.value[device.id] = []

  // Find manufacturer by name and load models
  const manufacturer = props.filterData.manufacturers.find(m => m.name === device.manufacturer)
  if (manufacturer) {
    editForms.value[device.id].manufacturer_id = manufacturer.id
    loadModelsForManufacturer(device.id)
  }
}

function cancelEdit(deviceId) {
  // Remove from editing set
  editingIds.value.delete(deviceId)

  // Clean up form and models
  delete editForms.value[deviceId]
  delete availableModelsMap.value[deviceId]
  delete pdfFiles.value[deviceId]
}

function onPdfSelected(deviceId, event) {
  const files = Array.from(event.target.files)
  const invalid = files.find(f => !f.name.toLowerCase().endsWith('.pdf'))
  if (invalid) {
    showToast('Ошибка', `«${invalid.name}»: допускается только PDF`, 'error')
    event.target.value = ''
    pdfFiles.value[deviceId] = []
    return
  }
  pdfFiles.value[deviceId] = files
}

const pdfDropTargetId = ref(null)

function onPdfDragOver(device, event) {
  if (!canEditDevices.value) return
  event.preventDefault()
  pdfDropTargetId.value = device.id
}

async function onPdfDrop(device, event) {
  pdfDropTargetId.value = null
  if (!canEditDevices.value) return
  event.preventDefault()

  const files = Array.from(event.dataTransfer?.files || [])
  if (!files.length) return

  const invalid = files.find(f => !f.name.toLowerCase().endsWith('.pdf'))
  if (invalid) {
    showToast('Ошибка', `«${invalid.name}»: допускается только PDF`, 'error')
    return
  }

  try {
    const fd = new FormData()
    files.forEach(f => fd.append('files', f))
    const response = await fetch(`/contracts/api/${device.id}/acceptance-docs/upload/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: fd
    })
    const data = await response.json()
    if (!data.ok) {
      showToast('Ошибка', data.error || 'Не удалось загрузить PDF', 'error')
      return
    }
    device.acceptance_docs = [...(device.acceptance_docs || []), ...data.documents]
    showToast('Успех', `Загружено файлов: ${data.documents.length}`, 'success')
  } catch (error) {
    console.error('Error uploading acceptance docs:', error)
    showToast('Ошибка', 'Не удалось загрузить PDF', 'error')
  }
}

function formatDocDate(isoDate) {
  if (!isoDate) return ''
  return new Date(isoDate).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function deleteAcceptanceDoc(device, doc) {
  if (!confirm(`Удалить файл «${doc.name}»?`)) return

  try {
    const response = await fetch(`/contracts/api/acceptance-docs/${doc.id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    })
    const data = await response.json()
    if (data.ok) {
      device.acceptance_docs = device.acceptance_docs.filter(d => d.id !== doc.id)
      showToast('Успех', 'Файл удалён', 'success')
    } else {
      showToast('Ошибка', data.error || 'Не удалось удалить файл', 'error')
    }
  } catch (error) {
    console.error('Error deleting acceptance doc:', error)
    showToast('Ошибка', 'Не удалось удалить файл', 'error')
  }
}

async function loadModelsForManufacturer(deviceId) {
  const form = editForms.value[deviceId]
  if (!form || !form.manufacturer_id) {
    availableModelsMap.value[deviceId] = []
    if (form) {
      form.model_id = ''
    }
    return
  }

  try {
    const response = await fetch(
      `/contracts/api/models-by-manufacturer/?manufacturer_id=${form.manufacturer_id}`
    )
    const data = await response.json()
    const models = data.models || []
    availableModelsMap.value[deviceId] = models
    if (form.model_id && !models.some(m => String(m.id) === String(form.model_id))) {
      form.model_id = ''
    }
  } catch (error) {
    console.error('Error loading models:', error)
    showToast('Ошибка', 'Не удалось загрузить модели', 'error')
  }
}

async function saveEdit(deviceId) {
  const form = editForms.value[deviceId]
  if (!form) return

  // Add device to saving set
  isSaving.value.add(deviceId)

  try {
    const payload = {
      status_id: parseInt(form.status_id),
      service_start_month: form.service_start_month || null,
      initial_counter: form.initial_counter === '' ? null : parseInt(form.initial_counter)
    }

    if (fullEdit.value) {
      Object.assign(payload, {
        organization_id: parseInt(form.organization_id),
        city_id: parseInt(form.city_id),
        address: form.address,
        room_number: form.room_number,
        model_id: parseInt(form.model_id),
        serial_number: form.serial_number,
        comment: form.comment
      })
      if (form.service_provider_id) {
        payload.service_provider_id = parseInt(form.service_provider_id)
      }
    }

    const response = await fetch(`/contracts/api/${deviceId}/update/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()

    if (data.ok) {
      const pdfOk = await uploadAcceptanceDocs(deviceId)
      showToast('Успех', 'Устройство обновлено', 'success')
      if (pdfOk) {
        emit('saved')
        cancelEdit(deviceId)
      }
    } else {
      showToast('Ошибка', data.error || 'Не удалось сохранить изменения', 'error')
    }
  } catch (error) {
    console.error('Error saving device:', error)
    showToast('Ошибка', 'Не удалось сохранить устройство', 'error')
  } finally {
    // Remove from saving set
    isSaving.value.delete(deviceId)
  }
}

async function uploadAcceptanceDocs(deviceId) {
  const files = pdfFiles.value[deviceId]
  if (!files || !files.length) return true

  try {
    const fd = new FormData()
    files.forEach(f => fd.append('files', f))
    const response = await fetch(`/contracts/api/${deviceId}/acceptance-docs/upload/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: fd
    })
    const data = await response.json()
    if (!data.ok) {
      showToast('Ошибка', data.error || 'Не удалось загрузить PDF', 'error')
      return false
    }
    return true
  } catch (error) {
    console.error('Error uploading acceptance docs:', error)
    showToast('Ошибка', 'Не удалось загрузить PDF', 'error')
    return false
  }
}

// GLPI functions
function isCheckingGLPI(deviceId) {
  return checkingGLPI.value.has(deviceId)
}

function isLocationMismatch(device) {
  if (!device.glpi_location || !device.city) return false
  return !device.glpi_location.toLowerCase().includes(device.city.toLowerCase())
}

function getGLPIStatusClass(status) {
  const classes = {
    'FOUND_SINGLE': 'bg-success',
    'FOUND_MULTIPLE': 'bg-warning text-dark',
    'NOT_FOUND': 'bg-secondary',
    'ERROR': 'bg-danger'
  }
  return classes[status] || 'bg-secondary'
}

function formatGLPIDate(isoDate) {
  if (!isoDate) return ''

  try {
    const date = new Date(isoDate)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'только что'
    if (diffMins < 60) return `${diffMins} мин назад`
    if (diffHours < 24) return `${diffHours} ч назад`
    if (diffDays < 7) return `${diffDays} д назад`

    // Otherwise format as date
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
  } catch (e) {
    return isoDate
  }
}

async function checkInGLPI(deviceId) {
  // Add to checking set
  checkingGLPI.value.add(deviceId)

  try {
    const response = await fetch(`/integrations/glpi/check-device/${deviceId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ force: true })
    })

    const data = await response.json()

    if (data.ok) {
      const sync = data.sync

      // Find device in props and update GLPI data
      const device = props.devices.find(d => d.id === deviceId)
      if (device) {
        device.glpi_status = sync.status
        device.glpi_status_display = sync.status_display
        device.glpi_count = sync.glpi_count
        device.glpi_ids = sync.glpi_ids
        device.glpi_checked_at = sync.checked_at
        device.glpi_is_synced = sync.is_synced
        device.glpi_has_conflict = sync.has_conflict
        device.glpi_state_id = sync.glpi_state_id
        device.glpi_state_name = sync.glpi_state_name
        if (sync.glpi_location !== undefined) {
          device.glpi_location = sync.glpi_location
        }
      }

      // Show appropriate toast
      if (sync.has_conflict) {
        showToast('Внимание', `Найдено несколько карточек (${sync.glpi_count})`, 'warning')
      } else if (sync.status === 'FOUND_SINGLE') {
        showToast('Успех', 'Устройство найдено в GLPI', 'success')
      } else if (sync.status === 'NOT_FOUND') {
        showToast('Информация', 'Устройство не найдено в GLPI', 'info')
      } else if (sync.status === 'ERROR') {
        showToast('Ошибка', sync.error_message || 'Ошибка при проверке', 'error')
      }
    } else {
      showToast('Ошибка', data.error || 'Не удалось проверить устройство', 'error')
    }
  } catch (error) {
    console.error('GLPI check error:', error)
    showToast('Ошибка', 'Не удалось проверить устройство в GLPI', 'error')
  } finally {
    // Remove from checking set
    checkingGLPI.value.delete(deviceId)
  }
}
</script>

<style>
/* подсветка ячейки при перетаскивании PDF */
.col-initial-counter.pdf-drop-active {
  outline: 2px dashed var(--bs-primary);
  outline-offset: -2px;
  background-color: rgba(13, 110, 253, 0.08);
}

/* таблица + заголовки */
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

.table-fixed thead th {
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  position: relative;
  padding-right: 10px; /* место под ручку */
}

/* .table-responsive — внешний контейнер, без скролла */
.table-responsive {
  overflow: visible;
}

/* .table-wrapper — контейнер горизонтального скролла (нативный скроллбар) */
.table-wrapper {
  position: relative;
  width: 100%;
  overflow-x: auto;
}

/* тело таблицы — переносы */
.table-fixed tbody td {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
}

/* узкие ячейки — без переносов */
.table-fixed td.col-serial,
.table-fixed td.col-room,
.table-fixed td.col-status,
.table-fixed td.col-service-month,
.table-fixed td.col-actions {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* кнопки действий */
.col-actions {
  text-align: center;
  white-space: nowrap;
}

.action-group .btn-icon {
  width: 2rem;
  height: 2rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.action-group .btn-icon i {
  font-size: 1rem;
  line-height: 1;
}

/* подсветка редактируемой строки */
tr.editing {
  background: var(--pi-table-row-hover, rgba(13, 110, 253, 0.05));
}

[data-bs-theme="dark"] tr.editing {
  background: rgba(66, 153, 225, 0.1);
}

/* Column resize handles */
.col-resize-handle {
  position: absolute;
  top: 0;
  right: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  user-select: none;
  z-index: 1;
}

.col-resize-handle::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  right: 2px;
  border-right: 1px dashed var(--pi-border-color, rgba(0, 0, 0, 0.2));
}

.col-resize-handle.active::after {
  border-right-color: var(--bs-primary);
  border-right-width: 2px;
  border-right-style: solid;
}

.col-resize-handle:hover::after {
  border-right-color: var(--pi-input-focus-border, rgba(0, 123, 255, 0.5));
}

.form-control-sm,
.form-select-sm {
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
}

.badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}

/* GLPI column */
.col-glpi {
  white-space: nowrap;
  font-size: 0.875rem;
}

.col-glpi .badge {
  font-size: 0.7rem;
}

/* Spinning animation for GLPI check */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.spin {
  animation: spin 1s linear infinite;
}

/* Перетаскивание колонок за заголовки */
.table-fixed thead th[draggable="true"] {
  cursor: grab;
}

.table-fixed thead th.th-dragging {
  opacity: 0.5;
  cursor: grabbing;
}

/* подсветка всей перетаскиваемой колонки */
col.cg-dragging {
  background-color: rgba(13, 110, 253, 0.07);
}

/* маркер места вставки */
.table-fixed thead th.th-drop-left {
  box-shadow: inset 3px 0 0 var(--bs-primary);
}

.table-fixed thead th.th-drop-right {
  box-shadow: inset -3px 0 0 var(--bs-primary);
}
</style>
