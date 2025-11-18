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

    table.querySelectorAll('th').forEach((th, index) => {
      const width = widths[index]
      if (width) {
        th.style.width = width
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

    function onMouseMove(e) {
      const dx = e.clientX - startX
      const newWidth = Math.max(60, startWidth + dx)
      th.style.width = newWidth + 'px'
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
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    }

    function onDoubleClick(e) {
      e.preventDefault()
      e.stopPropagation()
      th.style.width = ''

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
    if (!table) return

    // Load saved widths
    const savedWidths = loadColumnWidths()
    applyColumnWidths(table, savedWidths)

    // Add resize handles to all headers except the last one (actions column)
    const headers = table.querySelectorAll('thead th')
    headers.forEach((th, index) => {
      // Skip first column (№) and last column (Действия)
      if (index === 0 || index === headers.length - 1) return

      const { handle, cleanup } = createResizeHandle(th, index)
      resizeHandles.push({ handle, cleanup })
    })
  }

  function cleanupResize() {
    resizeHandles.forEach(({ cleanup }) => cleanup())
    resizeHandles = []
  }

  onMounted(() => {
    setTimeout(initResize, 100)
  })

  onUnmounted(() => {
    cleanupResize()
  })

  return {
    initResize,
    cleanupResize
  }
}
