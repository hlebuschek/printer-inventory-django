import { computed } from 'vue'

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

        const reportValue = String(report[column] || '').toLowerCase()
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

    reports.forEach(report => {
      const value = report[column]
      if (value !== null && value !== undefined && value !== '') {
        values.add(String(value))
      }
    })

    return Array.from(values).sort((a, b) => a.localeCompare(b, 'ru'))
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
