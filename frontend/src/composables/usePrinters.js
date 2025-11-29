import { usePrinterStore } from '@/stores/printerStore'
import { useToast } from './useToast'
import { printersApi } from '@/utils/api'

export function usePrinters() {
  const printerStore = usePrinterStore()
  const { showToast } = useToast()

  async function fetchPrinters(params = {}) {
    try {
      await printerStore.fetchPrinters(params)
    } catch (error) {
      showToast({
        title: 'Ошибка загрузки',
        message: 'Не удалось загрузить список принтеров',
        type: 'error'
      })
    }
  }

  async function runInventory(printerId) {
    try {
      await printerStore.runInventory(printerId)

      showToast({
        title: 'Опрос запущен',
        message: `Опрос принтера ${printerId} начат`,
        type: 'info',
        duration: 3000
      })
    } catch (error) {
      showToast({
        title: 'Ошибка запуска опроса',
        message: error.message,
        type: 'error'
      })
    }
  }

  async function runInventoryAll() {
    try {
      await printerStore.runInventoryAll()

      showToast({
        title: 'Опрос запущен',
        message: 'Опрос всех принтеров начат',
        type: 'info',
        duration: 3000
      })
    } catch (error) {
      showToast({
        title: 'Ошибка запуска опроса',
        message: error.message,
        type: 'error'
      })
    }
  }

  async function deletePrinter(printerId) {
    try {
      await printersApi.delete(printerId)

      // Обновляем список
      await fetchPrinters()

      showToast({
        title: 'Успешно',
        message: 'Принтер удален',
        type: 'success'
      })
    } catch (error) {
      showToast({
        title: 'Ошибка удаления',
        message: error.message,
        type: 'error'
      })
      throw error
    }
  }

  async function updatePrinter(printerId, data) {
    try {
      const result = await printersApi.update(printerId, data)

      if (result.success) {
        // Обновляем список
        await fetchPrinters()

        showToast({
          title: 'Успешно',
          message: 'Принтер обновлен',
          type: 'success'
        })

        return result
      } else {
        throw new Error(result.error || 'Неизвестная ошибка')
      }
    } catch (error) {
      showToast({
        title: 'Ошибка обновления',
        message: error.message,
        type: 'error'
      })
      throw error
    }
  }

  return {
    printerStore,
    fetchPrinters,
    runInventory,
    runInventoryAll,
    deletePrinter,
    updatePrinter
  }
}
