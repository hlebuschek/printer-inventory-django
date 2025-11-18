<template>
  <div class="table-responsive">
    <table class="table table-striped table-bordered">
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
</template>

<script setup>
import { computed } from 'vue'

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
</style>
