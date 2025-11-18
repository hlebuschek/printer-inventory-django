import { ref } from 'vue'

const toasts = ref([])
let toastId = 0

export function useToast() {
  /**
   * Показать toast уведомление
   * Поддерживает два синтаксиса:
   * 1. showToast({ title, message, type, duration })
   * 2. showToast(title, message, type, duration)
   */
  function showToast(titleOrOptions, message, type = 'info', duration = 5000) {
    let title, finalMessage, finalType, finalDuration

    // Проверяем, передан ли объект или отдельные параметры
    if (typeof titleOrOptions === 'object' && titleOrOptions !== null && !Array.isArray(titleOrOptions)) {
      // Объектный синтаксис
      ({ title, message: finalMessage, type: finalType = 'info', duration: finalDuration = 5000 } = titleOrOptions)
    } else {
      // Позиционные параметры
      title = titleOrOptions
      finalMessage = message
      finalType = type
      finalDuration = duration
    }

    const id = ++toastId

    const toast = {
      id,
      title,
      message: finalMessage,
      type: finalType, // info, success, warning, error
      visible: true
    }

    toasts.value.push(toast)

    // Автоматически скрывать через duration мс
    if (finalDuration > 0) {
      setTimeout(() => {
        hideToast(id)
      }, finalDuration)
    }

    return id
  }

  function hideToast(id) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }

  function clearAll() {
    toasts.value = []
  }

  return {
    toasts,
    showToast,
    hideToast,
    clearAll
  }
}
