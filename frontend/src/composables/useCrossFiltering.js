import { computed } from 'vue'

/**
 * Маппинг column key → field name в report объекте
 * Используется когда имя колонки для фильтра отличается от имени поля в данных
 */
const COLUMN_TO_FIELD_MAP = {
  'total': 'total_prints',  // Колонка 'total' → поле 'total_prints'
  'num': 'order_number',    // Колонка 'num' → поле 'order_number'
}

/**
 * Composable for cross-filtering column choices
 * Updates available filter options based on currently applied filters
 *
 * @param {Ref<Array>} allReports - All reports data
 * @param {Ref<Object>} activeFilters - Currently active filters { column: value }
 * @param {Array<string>} columns - List of column keys to generate choices for
 * @returns {ComputedRef<Object>} Dynamically filtered choices for each column
 */
export function useCrossFiltering(allReports, activeFilters, columns) {
  /**
   * Get filtered reports based on active filters (excluding one column)
   */
  const getFilteredReports = (excludeColumn = null) => {
    return allReports.value.filter(report => {
      // Check each active filter
      for (const [column, filterValue] of Object.entries(activeFilters.value)) {
        // Skip the excluded column (the one we're calculating choices for)
        if (column === excludeColumn) continue

        // Skip empty filters
        if (!filterValue) continue

        // Получаем имя поля с учётом маппинга
        const fieldName = COLUMN_TO_FIELD_MAP[column] || column
        const reportValue = String(report[fieldName] || '').toLowerCase()
        const filters = String(filterValue).toLowerCase().split('||').map(v => v.trim())

        // Check if report matches any of the filter values
        const matches = filters.some(filter => {
          if (filter.includes('*')) {
            // Wildcard search
            const regex = new RegExp(filter.replace(/\*/g, '.*'), 'i')
            return regex.test(reportValue)
          } else {
            // Exact or contains search
            return reportValue.includes(filter)
          }
        })

        if (!matches) return false
      }

      return true
    })
  }

  /**
   * Get unique values for a column from filtered reports
   */
  const getUniqueValues = (column, reports) => {
    const values = new Set()

    // Получаем имя поля с учётом маппинга
    const fieldName = COLUMN_TO_FIELD_MAP[column] || column

    reports.forEach(report => {
      const value = report[fieldName]
      if (value !== null && value !== undefined && value !== '') {
        values.add(String(value))
      }
    })

    // Для числовых полей (total, num) используем числовую сортировку
    const isNumericField = ['total', 'num'].includes(column)

    return Array.from(values).sort((a, b) => {
      if (isNumericField) {
        return parseInt(a) - parseInt(b)
      }
      return a.localeCompare(b, 'ru')
    })
  }

  /**
   * Computed property that returns dynamically filtered choices
   */
  const filteredChoices = computed(() => {
    const choices = {}

    columns.forEach(column => {
      // Get reports filtered by all filters EXCEPT this column
      const filtered = getFilteredReports(column)

      // Get unique values for this column from filtered reports
      choices[column] = getUniqueValues(column, filtered)
    })

    return choices
  })

  return {
    filteredChoices
  }
}
