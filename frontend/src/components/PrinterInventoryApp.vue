<template>
  <div id="vue-printer-inventory">
    <!-- Toast уведомления -->
    <ToastContainer />

    <!-- Основной контент -->
    <div class="printer-inventory-content">
      <h2 class="mb-4">🚀 Vue.js успешно подключен!</h2>

      <div class="alert alert-success" role="alert">
        <h4 class="alert-heading">Миграция на Vue.js начата</h4>
        <p>Приложение успешно инициализировано и готово к разработке.</p>
        <hr>
        <p class="mb-0">
          <strong>Статус:</strong> WebSocket {{ wsConnected ? '✅ Подключен' : '❌ Отключен' }}
        </p>
        <p class="mb-0">
          <strong>Принтеров загружено:</strong> {{ printerStore.printers.length }}
        </p>
        <p class="mb-0">
          <strong>CSRF Token:</strong> {{ csrfToken ? '✅ Найден' : '❌ Не найден' }}
        </p>
      </div>

      <!-- Тестовая кнопка для проверки toast -->
      <div class="mt-3">
        <button class="btn btn-primary me-2" @click="testToast">
          Тестовое уведомление
        </button>

        <button class="btn btn-success me-2" @click="testWebSocket">
          Тест WebSocket
        </button>

        <button class="btn btn-info" @click="loadPrinters">
          Загрузить принтеры (API тест)
        </button>
      </div>

      <!-- Счетчик для проверки реактивности -->
      <div class="card mt-4" style="max-width: 400px;">
        <div class="card-body">
          <h5 class="card-title">Тест реактивности Vue</h5>
          <p class="display-4 text-center mb-3">{{ counter }}</p>
          <div class="d-flex gap-2">
            <button class="btn btn-primary flex-fill" @click="counter++">+1</button>
            <button class="btn btn-secondary flex-fill" @click="counter--">-1</button>
            <button class="btn btn-outline-danger flex-fill" @click="counter = 0">Сброс</button>
          </div>
        </div>
      </div>

      <!-- Список принтеров (если загружены) -->
      <div v-if="printerStore.printers.length > 0" class="mt-4">
        <h4>Загруженные принтеры:</h4>
        <ul class="list-group">
          <li
            v-for="printer in printerStore.printers.slice(0, 5)"
            :key="printer.id"
            class="list-group-item"
          >
            <strong>{{ printer.ip_address || printer.printer?.ip_address }}</strong> -
            {{ printer.serial_number || printer.printer?.serial_number }}
          </li>
        </ul>
        <p class="text-muted mt-2">
          <small>Показано 5 из {{ printerStore.printers.length }}</small>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { usePrinterStore } from '@/stores/printerStore'
import { useWebSocket } from '@/composables/useWebSocket'
import { useToast } from '@/composables/useToast'
import { usePrinters } from '@/composables/usePrinters'
import ToastContainer from './common/ToastContainer.vue'

// Получаем конфиг от Django
const appConfig = inject('appConfig', {})
const csrfToken = ref(appConfig.csrfToken)

// Stores и composables
const printerStore = usePrinterStore()
const { connected: wsConnected } = useWebSocket()
const { showToast } = useToast()
const { fetchPrinters } = usePrinters()

// Тестовый счетчик для проверки реактивности
const counter = ref(0)

// Тестовые функции
function testToast() {
  const types = ['success', 'error', 'warning', 'info']
  const type = types[Math.floor(Math.random() * types.length)]

  showToast({
    title: `Тестовое уведомление (${type})`,
    message: `Это тестовое сообщение типа ${type}`,
    type,
    duration: 5000
  })
}

function testWebSocket() {
  showToast({
    title: 'WebSocket тест',
    message: wsConnected.value
      ? 'WebSocket подключен и работает!'
      : 'WebSocket не подключен',
    type: wsConnected.value ? 'success' : 'error'
  })
}

async function loadPrinters() {
  showToast({
    title: 'Загрузка...',
    message: 'Загружаем список принтеров',
    type: 'info',
    duration: 2000
  })

  try {
    await fetchPrinters()

    showToast({
      title: 'Успешно!',
      message: `Загружено ${printerStore.printers.length} принтеров`,
      type: 'success'
    })
  } catch (error) {
    showToast({
      title: 'Ошибка',
      message: 'Не удалось загрузить принтеры',
      type: 'error'
    })
  }
}

onMounted(() => {
  console.log('✅ PrinterInventoryApp mounted')
  console.log('App config:', appConfig)
})
</script>

<style scoped>
#vue-printer-inventory {
  min-height: 300px;
}

.printer-inventory-content {
  animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
