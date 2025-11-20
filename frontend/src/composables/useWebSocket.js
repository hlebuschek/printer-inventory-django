import { ref, onMounted, onUnmounted } from 'vue'
import { usePrinterStore } from '@/stores/printerStore'
import { useToast } from './useToast'

export function useWebSocket() {
  const ws = ref(null)
  const connected = ref(false)
  const printerStore = usePrinterStore()
  const { showToast } = useToast()

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${location.host}/ws/inventory/`

    try {
      ws.value = new WebSocket(wsUrl)

      ws.value.onopen = () => {
        connected.value = true
        console.log('✅ WebSocket connected')
      }

      ws.value.onclose = () => {
        connected.value = false
        console.log('❌ WebSocket disconnected')

        // Переподключение через 5 секунд
        setTimeout(() => {
          if (!connected.value) {
            console.log('🔄 Reconnecting WebSocket...')
            connect()
          }
        }, 5000)
      }

      ws.value.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleMessage(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
      connected.value = false
    }
  }

  function handleMessage(data) {
    const { type, printer_id, status, message, triggered_by } = data

    if (type === 'inventory_start') {
      // Опрос начался - просто показываем спиннер (уже в store)
      console.log(`📡 Inventory started for printer ${printer_id} (triggered by: ${triggered_by || 'manual'})`)
      return
    }

    if (type === 'inventory_update') {
      // Определяем, нужно ли показывать toast
      // Показываем toast только если:
      // 1. Ручной опрос (triggered_by === 'manual') - всегда
      // 2. Автоматический опрос (triggered_by === 'daemon') - только при ошибке
      const shouldShowToast = triggered_by === 'manual' || (triggered_by === 'daemon' && status !== 'SUCCESS')

      if (status === 'HISTORICAL_INCONSISTENCY') {
        // Исторические данные не согласованы
        if (shouldShowToast) {
          showToast({
            title: 'Исторические данные не согласованы',
            message: `Принтер ${printer_id}: ${message}`,
            type: 'warning',
            duration: 10000
          })
        }

        // Убираем спиннер
        printerStore.pollingPrinters.delete(printer_id)

        // Отправляем событие для обновления списка принтеров
        window.dispatchEvent(new CustomEvent('printer-updated', {
          detail: { printerId: printer_id, status, data }
        }))
        return
      }

      if (status === 'FAILED' || status === 'VALIDATION_ERROR') {
        // Ошибка опроса
        if (shouldShowToast) {
          showToast({
            title: 'Ошибка опроса',
            message: `Принтер ${printer_id}: ${message}`,
            type: 'error',
            duration: 8000
          })
        }

        // Убираем спиннер
        printerStore.pollingPrinters.delete(printer_id)

        // Отправляем событие для обновления списка принтеров
        window.dispatchEvent(new CustomEvent('printer-updated', {
          detail: { printerId: printer_id, status, data }
        }))
        return
      }

      // SUCCESS - обновляем данные принтера
      if (status === 'SUCCESS' || !status) {
        printerStore.updatePrinterFromWebSocket(data)

        if (shouldShowToast) {
          showToast({
            title: 'Опрос завершен',
            message: `Данные принтера ${printer_id} успешно обновлены`,
            type: 'success',
            duration: 3000
          })
        }

        // Отправляем событие для обновления списка принтеров с данными
        window.dispatchEvent(new CustomEvent('printer-updated', {
          detail: { printerId: printer_id, status, data }
        }))
      }
    }
  }

  function send(data) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket is not connected')
    }
  }

  // Автоматическое подключение при монтировании
  onMounted(() => {
    connect()
  })

  // Отключение при размонтировании
  onUnmounted(() => {
    disconnect()
  })

  return {
    ws,
    connected,
    connect,
    disconnect,
    send
  }
}
