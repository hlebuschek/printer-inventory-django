import { ref } from 'vue'

const toasts = ref([])
let toastId = 0

export function useToast() {
  function showToast({ title, message, type = 'info', duration = 5000 }) {
    const id = ++toastId

    const toast = {
      id,
      title,
      message,
      type, // info, success, warning, error
      visible: true
    }

    toasts.value.push(toast)

    // Автоматически скрывать через duration мс
    if (duration > 0) {
      setTimeout(() => {
        hideToast(id)
      }, duration)
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
