<template>
  <div>
    <div class="table-responsive" ref="tableWrapper">
      <table class="table table-striped table-bordered" ref="table">
        <thead>
          <tr>
            <th v-if="isColumnVisible('organization')">Организация</th>
            <th v-if="isColumnVisible('ip_address')">IP-адрес</th>
            <th v-if="isColumnVisible('serial_number')">Серийный №</th>
            <th v-if="isColumnVisible('mac_address')">MAC-адрес</th>
            <th v-if="isColumnVisible('device_model')">Модель</th>
            <th v-if="isColumnVisible('bw_a4')">ЧБ A4</th>
            <th v-if="isColumnVisible('color_a4')">Цвет A4</th>
            <th v-if="isColumnVisible('bw_a3')">ЧБ A3</th>
            <th v-if="isColumnVisible('color_a3')">Цвет A3</th>
            <th v-if="isColumnVisible('total')">Всего</th>
            <th v-if="isColumnVisible('drums')">Барабаны (K/C/M/Y)</th>
            <th v-if="isColumnVisible('toners')">Тонеры (K/C/M/Y)</th>
            <th v-if="isColumnVisible('fuser_kit')">Fuser Kit</th>
            <th v-if="isColumnVisible('transfer_kit')">Transfer Kit</th>
            <th v-if="isColumnVisible('waste_toner')">Waste Toner</th>
            <th v-if="isColumnVisible('timestamp')">Дата опроса</th>
            <th v-if="isColumnVisible('match_rule')">Правило</th>
            <th v-if="isColumnVisible('actions') && hasActionPermissions">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="printer in printers"
            :key="printer.id"
            :data-printer-id="printer.id"
            :class="{ 'table-success': printer.is_fresh }"
          >
            <td v-if="isColumnVisible('organization')">
              {{ printer.organization?.name || '—' }}
            </td>

            <td v-if="isColumnVisible('ip_address')">
              {{ printer.ip_address }}
              <span
                v-if="printer.is_fresh"
                class="badge bg-success ms-1"
                title="Свежие данные из последнего опроса"
              >
                <i class="bi bi-check-circle"></i> Обновлено
              </span>
            </td>

            <td v-if="isColumnVisible('serial_number')">
              {{ printer.serial_number }}
            </td>

            <td v-if="isColumnVisible('mac_address')">
              {{ printer.mac_address || '—' }}
            </td>

            <td v-if="isColumnVisible('device_model')">
              {{ printer.device_model?.name || '—' }}
            </td>

            <td v-if="isColumnVisible('bw_a4')">
              {{ printer.counters?.bw_a4 || '—' }}
            </td>

            <td v-if="isColumnVisible('color_a4')">
              {{ printer.counters?.color_a4 || '—' }}
            </td>

            <td v-if="isColumnVisible('bw_a3')">
              {{ printer.counters?.bw_a3 || '—' }}
            </td>

            <td v-if="isColumnVisible('color_a3')">
              {{ printer.counters?.color_a3 || '—' }}
            </td>

            <td v-if="isColumnVisible('total')">
              {{ printer.counters?.total || '—' }}
            </td>

            <td v-if="isColumnVisible('drums')">
              {{ printer.counters?.drum_black || '—' }} /
              {{ printer.counters?.drum_cyan || '—' }} /
              {{ printer.counters?.drum_magenta || '—' }} /
              {{ printer.counters?.drum_yellow || '—' }}
            </td>

            <td v-if="isColumnVisible('toners')">
              {{ printer.counters?.toner_black || '—' }} /
              {{ printer.counters?.toner_cyan || '—' }} /
              {{ printer.counters?.toner_magenta || '—' }} /
              {{ printer.counters?.toner_yellow || '—' }}
            </td>

            <td v-if="isColumnVisible('fuser_kit')">
              {{ printer.counters?.fuser_kit || '—' }}
            </td>

            <td v-if="isColumnVisible('transfer_kit')">
              {{ printer.counters?.transfer_kit || '—' }}
            </td>

            <td v-if="isColumnVisible('waste_toner')">
              {{ printer.counters?.waste_toner || '—' }}
            </td>

            <td v-if="isColumnVisible('timestamp')">
              {{ formatDate(printer.last_date) }}
            </td>

            <td v-if="isColumnVisible('match_rule')">
              <span
                class="match-dot"
                :class="getMatchRuleClass(printer.last_match_rule)"
                :title="getMatchRuleTitle(printer.last_match_rule)"
              ></span>
            </td>

            <td v-if="isColumnVisible('actions') && hasActionPermissions">
              <button
                v-if="permissions.change_printer"
                class="btn btn-sm btn-outline-primary me-1"
                title="Редактировать"
                @click="$emit('edit', printer.id)"
              >
                <i class="bi bi-pencil"></i>
              </button>

              <button
                v-if="permissions.manage_web_parsing"
                class="btn btn-sm btn-outline-secondary me-1"
                title="Настроить веб-парсинг"
                @click="$emit('web-parser', printer.id)"
              >
                <i class="bi bi-globe"></i>
              </button>

              <button
                v-if="permissions.delete_printer"
                class="btn btn-sm btn-outline-danger me-1"
                title="Удалить"
                @click="$emit('delete', printer)"
              >
                <i class="bi bi-trash"></i>
              </button>

              <button
                class="btn btn-sm btn-outline-info me-1"
                title="Скачать письмо с информацией"
                @click="$emit('email', printer)"
              >
                <i class="bi bi-envelope"></i>
              </button>

              <button
                class="btn btn-sm btn-outline-primary me-1"
                title="Информация и история"
                @click="$emit('history', printer.id)"
              >
                <i class="bi bi-clock-history"></i>
              </button>

              <button
                v-if="permissions.run_inventory || permissions.change_printer"
                class="btn btn-sm btn-outline-primary"
                title="Опрос"
                :disabled="isRunning(printer.id)"
                @click="$emit('run-poll', printer.id)"
              >
                <span
                  v-if="isRunning(printer.id)"
                  class="spinner-border spinner-border-sm me-1"
                ></span>
                <i v-else class="bi bi-arrow-repeat"></i>
              </button>
            </td>
          </tr>

          <tr v-if="!printers.length">
            <td :colspan="visibleColumnCount" class="text-center">
              Принтеры не найдены
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Fixed Scrollbar -->
    <div ref="fixedScrollbar" class="fixed-scrollbar">
      <div ref="fixedScrollbarContent" class="fixed-scrollbar-content"></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  printers: {
    type: Array,
    required: true
  },
  visibleColumns: {
    type: Array,
    required: true
  },
  permissions: {
    type: Object,
    default: () => ({})
  },
  runningPrinters: {
    type: Set,
    default: () => new Set()
  }
})

const emit = defineEmits(['edit', 'delete', 'history', 'run-poll', 'email', 'web-parser'])

// Refs for scrollbar sync
const tableWrapper = ref(null)
const table = ref(null)
const fixedScrollbar = ref(null)
const fixedScrollbarContent = ref(null)
let mutationObserver = null

const hasActionPermissions = computed(() => {
  return (
    props.permissions.change_printer ||
    props.permissions.delete_printer ||
    props.permissions.run_inventory
  )
})

const visibleColumnCount = computed(() => {
  return props.visibleColumns.length
})

function isColumnVisible(columnKey) {
  return props.visibleColumns.includes(columnKey)
}

function isRunning(printerId) {
  return props.runningPrinters.has(printerId)
}

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
  } catch {
    return dateString
  }
}

function getMatchRuleClass(rule) {
  const classMap = {
    'SN_MAC': 'dot-sn-mac',
    'MAC_ONLY': 'dot-mac',
    'SN_ONLY': 'dot-sn'
  }
  return classMap[rule] || 'dot-unknown'
}

function getMatchRuleTitle(rule) {
  const titleMap = {
    'SN_MAC': 'Серийник + MAC',
    'MAC_ONLY': 'Только MAC',
    'SN_ONLY': 'Только серийник'
  }
  return titleMap[rule] || 'Нет данных'
}

// Fixed scrollbar sync
function syncScrollbarWidth() {
  if (!tableWrapper.value || !table.value || !fixedScrollbar.value || !fixedScrollbarContent.value) return

  const tableEl = table.value
  const wrapperEl = tableWrapper.value
  const scrollbarEl = fixedScrollbar.value
  const contentEl = fixedScrollbarContent.value

  // Set scrollbar content width equal to table width
  contentEl.style.width = `${tableEl.scrollWidth}px`

  // Show/hide scrollbar based on necessity
  if (tableEl.scrollWidth > wrapperEl.clientWidth) {
    scrollbarEl.style.display = 'block'
  } else {
    scrollbarEl.style.display = 'none'
  }
}

// Scroll sync handlers
function handleTableScroll() {
  if (fixedScrollbar.value && tableWrapper.value) {
    fixedScrollbar.value.scrollLeft = tableWrapper.value.scrollLeft
  }
}

function handleScrollbarScroll() {
  if (tableWrapper.value && fixedScrollbar.value) {
    tableWrapper.value.scrollLeft = fixedScrollbar.value.scrollLeft
  }
}

// Watch for printers or visible columns changes
watch(() => [props.printers, props.visibleColumns], () => {
  nextTick(() => {
    syncScrollbarWidth()
  })
}, { deep: true })

// Expose sync function for parent component
defineExpose({
  syncScrollbarWidth
})

onMounted(() => {
  // Initial sync
  nextTick(() => {
    syncScrollbarWidth()
  })

  // Setup event listeners
  if (tableWrapper.value) {
    tableWrapper.value.addEventListener('scroll', handleTableScroll)
  }
  if (fixedScrollbar.value) {
    fixedScrollbar.value.addEventListener('scroll', handleScrollbarScroll)
  }

  // Setup resize observer
  window.addEventListener('resize', syncScrollbarWidth)

  // Setup mutation observer for table changes
  if (tableWrapper.value) {
    mutationObserver = new MutationObserver(syncScrollbarWidth)
    mutationObserver.observe(tableWrapper.value, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style']
    })
  }
})

onUnmounted(() => {
  // Cleanup event listeners
  if (tableWrapper.value) {
    tableWrapper.value.removeEventListener('scroll', handleTableScroll)
  }
  if (fixedScrollbar.value) {
    fixedScrollbar.value.removeEventListener('scroll', handleScrollbarScroll)
  }
  window.removeEventListener('resize', syncScrollbarWidth)

  // Disconnect mutation observer
  if (mutationObserver) {
    mutationObserver.disconnect()
  }
})
</script>

<style scoped>
.match-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  vertical-align: middle;
}

.dot-sn-mac {
  background: #2ecc71;
}

.dot-mac {
  background: #f39c12;
}

.dot-sn {
  background: #3498db;
}

.dot-unknown {
  background: #95a5a6;
}

.table-success {
  transition: background-color 0.5s ease-out;
}

.badge.bg-success {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Fixed Scrollbar Styles */
.fixed-scrollbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 17px;
  background: rgba(248, 249, 250, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 1000;
  backdrop-filter: blur(3px);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  display: none;
}

.fixed-scrollbar-content {
  height: 1px;
}

.fixed-scrollbar::-webkit-scrollbar {
  height: 14px;
}

.fixed-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
}

.fixed-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 7px;
  border: 2px solid rgba(248, 249, 250, 0.95);
}

.fixed-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.5);
}

/* Add padding to body to prevent content from being hidden under scrollbar */
:deep(body) {
  padding-bottom: 20px;
}
</style>
