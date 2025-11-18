import { onMounted, onUnmounted } from 'vue'

export function useColumnResize(tableRef, storageKey) {
  let resizeHandles = []

  function saveColumnWidths(widths) {
    try {
      localStorage.setItem(storageKey, JSON.stringify(widths))
    } catch (error) {
      console.warn('Failed to save column widths:', error)
    }
  }

  function loadColumnWidths() {
    try {
      const saved = localStorage.getItem(storageKey)
      return saved ? JSON.parse(saved) : {}
    } catch (error) {
      console.warn('Failed to load column widths:', error)
      return {}
    }
  }

  function applyColumnWidths(table, widths) {
    if (!table) return

    const cols = table.querySelectorAll('colgroup col')
    table.querySelectorAll('th').forEach((th, index) => {
      const width = widths[index]
      if (width) {
        th.style.width = width
        // Also update col element if it exists
        if (cols[index]) {
          cols[index].style.width = width
        }
      }
    })
  }

  function createResizeHandle(th, index) {
    const handle = document.createElement('span')
    handle.className = 'col-resize-handle'
    th.style.position = 'relative'
    th.appendChild(handle)

    let startX = 0
    let startWidth = 0
    let col = null

    function onMouseMove(e) {
      const dx = e.clientX - startX
      const newWidth = Math.max(60, startWidth + dx)
      th.style.width = newWidth + 'px'

      // Also update corresponding col element
      if (col) {
        col.style.width = newWidth + 'px'
      }
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      handle.classList.remove('active')

      // Save column widths
      const table = tableRef.value?.$el || tableRef.value
      if (table) {
        const widths = {}
        table.querySelectorAll('th').forEach((th, idx) => {
          if (th.style.width) {
            widths[idx] = th.style.width
          }
        })
        saveColumnWidths(widths)
      }
    }

    function onMouseDown(e) {
      e.preventDefault()
      e.stopPropagation()
      startX = e.clientX
      startWidth = th.offsetWidth
      handle.classList.add('active')

      // Find corresponding col element
      const table = tableRef.value?.$el || tableRef.value
      if (table) {
        const cols = table.querySelectorAll('colgroup col')
        col = cols[index] || null
      }

      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    }

    function onDoubleClick(e) {
      e.preventDefault()
      e.stopPropagation()
      th.style.width = ''

      // Also reset col element
      const table = tableRef.value?.$el || tableRef.value
      if (table) {
        const cols = table.querySelectorAll('colgroup col')
        if (cols[index]) {
          cols[index].style.width = ''
        }
      }

      // Remove this column width from storage
      const widths = loadColumnWidths()
      delete widths[index]
      saveColumnWidths(widths)
    }

    handle.addEventListener('mousedown', onMouseDown)
    handle.addEventListener('dblclick', onDoubleClick)

    return {
      handle,
      cleanup: () => {
        handle.removeEventListener('mousedown', onMouseDown)
        handle.removeEventListener('dblclick', onDoubleClick)
      }
    }
  }

  function initResize() {
    const table = tableRef.value?.$el || tableRef.value
    if (!table) return false

    const headers = table.querySelectorAll('thead th')
    if (!headers || headers.length === 0) return false

    // Load saved widths
    const savedWidths = loadColumnWidths()
    applyColumnWidths(table, savedWidths)

    // Add resize handles to all headers except the last one (actions column)
    headers.forEach((th, index) => {
      // Skip first column (№) and last column (Действия)
      if (index === 0 || index === headers.length - 1) return

      const { handle, cleanup } = createResizeHandle(th, index)
      resizeHandles.push({ handle, cleanup })
    })

    return true
  }

  function tryInitResize(attempts = 0, maxAttempts = 20) {
    const success = initResize()

    if (!success && attempts < maxAttempts) {
      // Retry with exponential backoff
      const delay = Math.min(100 * (attempts + 1), 1000)
      setTimeout(() => tryInitResize(attempts + 1, maxAttempts), delay)
    } else if (!success) {
      console.warn('useColumnResize: failed to initialize after', maxAttempts, 'attempts')
    }
  }

  function cleanupResize() {
    resizeHandles.forEach(({ cleanup }) => cleanup())
    resizeHandles = []
  }

  onMounted(() => {
    tryInitResize()
  })

  onUnmounted(() => {
    cleanupResize()
  })

  return {
    initResize,
    cleanupResize
  }
}
