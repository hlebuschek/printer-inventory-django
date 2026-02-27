import { ref, onBeforeUnmount } from 'vue'

/**
 * Composable для виджетов дашборда с авто-повтором при ошибках.
 *
 * - Спиннер показывается только при первой загрузке
 * - При ошибке автоматически повторяет запрос с экспоненциальной задержкой
 * - Максимум retries попыток, потом ждёт следующего refreshTick
 * - При успешной загрузке сбрасывает счётчик ошибок
 */
export function useWidgetLoader({ maxRetries = 3, baseDelay = 5000, maxDelay = 60000 } = {}) {
  const loading = ref(true)
  const error = ref(null)
  const initialized = ref(false)

  let retryCount = 0
  let retryTimer = null

  /**
   * Обёртка вокруг функции загрузки данных.
   * @param {Function} fetchFn — async функция, выполняющая запрос.
   *   Должна бросить ошибку при неудаче.
   */
  async function execute(fetchFn) {
    if (!initialized.value) loading.value = true
    error.value = null
    clearRetryTimer()

    try {
      await fetchFn()
      // Успешно — сбрасываем счётчик
      initialized.value = true
      retryCount = 0
    } catch (e) {
      // Если уже есть данные, не показываем ошибку — просто повторим в фоне
      if (initialized.value) {
        console.warn('[widget] Фоновое обновление не удалось, повторяю...', e?.message)
      } else {
        error.value = 'Ошибка загрузки'
      }
      scheduleRetry(fetchFn)
    } finally {
      loading.value = false
    }
  }

  function scheduleRetry(fetchFn) {
    if (retryCount >= maxRetries) return
    retryCount++
    const delay = Math.min(baseDelay * Math.pow(2, retryCount - 1), maxDelay)
    retryTimer = setTimeout(() => execute(fetchFn), delay)
  }

  function clearRetryTimer() {
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
  }

  /** Сброс состояния (при смене фильтров) */
  function reset() {
    clearRetryTimer()
    initialized.value = false
    retryCount = 0
  }

  onBeforeUnmount(clearRetryTimer)

  return { loading, error, initialized, execute, reset, clearRetryTimer }
}
