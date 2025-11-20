import { watch, onMounted } from 'vue'

/**
 * Composable для синхронизации фильтров с URL query parameters
 *
 * @param {Object} filters - Reactive объект с фильтрами
 * @param {Function} onFiltersChanged - Callback при изменении фильтров из URL
 * @param {Object} options - Опции
 * @param {boolean} options.autoSync - Автоматически синхронизировать при изменении filters (по умолчанию false)
 * @returns {Object} - Методы для работы с URL
 */
export function useUrlFilters(filters, onFiltersChanged, options = {}) {
  const { autoSync = false } = options

  /**
   * Читает фильтры из URL и обновляет объект filters
   */
  function loadFiltersFromUrl() {
    const params = new URLSearchParams(window.location.search)
    let hasChanges = false

    // Проходим по всем параметрам URL и обновляем filters
    params.forEach((value, key) => {
      if (key in filters) {
        // Конвертируем числовые значения
        if (key === 'page' || key === 'per_page') {
          const numValue = parseInt(value)
          if (!isNaN(numValue) && filters[key] !== numValue) {
            filters[key] = numValue
            hasChanges = true
          }
        } else if (filters[key] !== value) {
          filters[key] = value
          hasChanges = true
        }
      }
    })

    // Вызываем callback если были изменения
    if (hasChanges && onFiltersChanged) {
      onFiltersChanged()
    }

    return hasChanges
  }

  /**
   * Сохраняет текущие фильтры в URL
   *
   * @param {boolean} replace - Использовать replaceState вместо pushState
   */
  function saveFiltersToUrl(replace = false) {
    const params = new URLSearchParams()

    // Добавляем только непустые значения
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) {
        // Не добавляем дефолтные значения для экономии места в URL
        if (key === 'page' && value === 1) return
        if (key === 'per_page' && value === 100) return

        params.set(key, String(value))
      }
    })

    const queryString = params.toString()
    const newUrl = queryString
      ? `${window.location.pathname}?${queryString}`
      : window.location.pathname

    // Обновляем URL без перезагрузки страницы
    if (replace) {
      window.history.replaceState({}, '', newUrl)
    } else {
      window.history.pushState({}, '', newUrl)
    }
  }

  /**
   * Очищает все фильтры из URL
   */
  function clearFiltersFromUrl() {
    window.history.pushState({}, '', window.location.pathname)
  }

  // Автоматическая синхронизация при изменении filters (опционально)
  if (autoSync) {
    watch(filters, () => {
      saveFiltersToUrl(true) // Используем replace для автосинхронизации
    }, { deep: true })
  }

  // Обработка кнопок назад/вперед браузера (popstate)
  onMounted(() => {
    const handlePopState = () => {
      loadFiltersFromUrl()
    }
    window.addEventListener('popstate', handlePopState)

    // Очистка при размонтировании
    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  })

  return {
    loadFiltersFromUrl,
    saveFiltersToUrl,
    clearFiltersFromUrl
  }
}
