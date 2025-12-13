import { ref, watch } from 'vue'

/**
 * Composable для управления видимостью столбцов таблицы с сохранением в localStorage
 * @param {string} storageKey - Ключ для localStorage
 * @param {Array<string>} allColumns - Все доступные столбцы
 * @param {Array<string>} defaultVisible - Столбцы, видимые по умолчанию
 */
export function useColumnVisibility(storageKey, allColumns, defaultVisible) {
  // Загружаем сохраненное состояние или используем defaults
  const loadState = () => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (!saved) return new Set(defaultVisible)

      const parsed = JSON.parse(saved)
      return Array.isArray(parsed) && parsed.length > 0
        ? new Set(parsed)
        : new Set(defaultVisible)
    } catch (error) {
      console.error('Error loading column visibility:', error)
      return new Set(defaultVisible)
    }
  }

  const visibleColumns = ref(loadState())

  // Сохраняем состояние при изменении
  const saveState = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify([...visibleColumns.value]))
    } catch (error) {
      console.error('Error saving column visibility:', error)
    }
  }

  // Автоматическое сохранение при изменении
  watch(visibleColumns, saveState, { deep: true })

  /**
   * Проверяет, виден ли столбец
   * @param {string} columnKey - Ключ столбца
   * @returns {boolean}
   */
  const isVisible = (columnKey) => {
    return visibleColumns.value.has(columnKey)
  }

  /**
   * Переключает видимость столбца
   * @param {string} columnKey - Ключ столбца
   */
  const toggle = (columnKey) => {
    if (visibleColumns.value.has(columnKey)) {
      visibleColumns.value.delete(columnKey)
    } else {
      visibleColumns.value.add(columnKey)
    }
    // Триггерим реактивность
    visibleColumns.value = new Set(visibleColumns.value)
  }

  /**
   * Показывает столбец
   * @param {string} columnKey - Ключ столбца
   */
  const show = (columnKey) => {
    if (!visibleColumns.value.has(columnKey)) {
      visibleColumns.value.add(columnKey)
      visibleColumns.value = new Set(visibleColumns.value)
    }
  }

  /**
   * Скрывает столбец
   * @param {string} columnKey - Ключ столбца
   */
  const hide = (columnKey) => {
    if (visibleColumns.value.has(columnKey)) {
      visibleColumns.value.delete(columnKey)
      visibleColumns.value = new Set(visibleColumns.value)
    }
  }

  /**
   * Сбрасывает к значениям по умолчанию
   */
  const reset = () => {
    visibleColumns.value = new Set(defaultVisible)
  }

  /**
   * Показывает все столбцы
   */
  const showAll = () => {
    visibleColumns.value = new Set(allColumns)
  }

  /**
   * Скрывает все столбцы
   */
  const hideAll = () => {
    visibleColumns.value = new Set()
  }

  return {
    visibleColumns,
    isVisible,
    toggle,
    show,
    hide,
    reset,
    showAll,
    hideAll
  }
}
