import { onMounted, onUnmounted } from 'vue'

export function useColumnResize(tableRef, storageKey) {
  let resizeHandles = []

  function getTable() {
    return tableRef.value?.$el || tableRef.value
  }

  // Ключ колонки: data-col-key (стабилен при перестановке колонок) либо индекс
  function thKey(th, index) {
    return th.dataset.colKey || String(index)
  }

  function thIndex(th) {
    return Array.prototype.indexOf.call(th.parentElement.children, th)
  }

  function colForTh(table, th) {
    const cols = table.querySelectorAll('colgroup col')
    return cols[thIndex(th)] || null
  }

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

    table.querySelectorAll('thead th').forEach((th, index) => {
      const width = widths[thKey(th, index)]
      if (width) {
        th.style.width = width
        const col = colForTh(table, th)
        if (col) {
          col.style.width = width
        }
      }
    })
  }

  function collectWidths(table) {
    const widths = {}
    table.querySelectorAll('thead th').forEach((th, index) => {
      if (th.style.width) {
        widths[thKey(th, index)] = th.style.width
      }
    })
    return widths
  }

  function createResizeHandle(th) {
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

      if (col) {
        col.style.width = newWidth + 'px'
      }
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      handle.classList.remove('active')

      const table = getTable()
      if (table) {
        saveColumnWidths(collectWidths(table))
      }
    }

    function onMouseDown(e) {
      e.preventDefault()
      e.stopPropagation()
      startX = e.clientX
      startWidth = th.offsetWidth
      handle.classList.add('active')

      const table = getTable()
      col = table ? colForTh(table, th) : null

      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    }

    function onDoubleClick(e) {
      e.preventDefault()
      e.stopPropagation()
      th.style.width = ''

      const table = getTable()
      if (table) {
        const col = colForTh(table, th)
        if (col) {
          col.style.width = ''
        }
      }

      const widths = loadColumnWidths()
      delete widths[thKey(th, thIndex(th))]
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
    const table = getTable()
    if (!table) return false

    const headers = table.querySelectorAll('thead th')
    if (!headers || headers.length === 0) return false

    const savedWidths = loadColumnWidths()
    applyColumnWidths(table, savedWidths)

    headers.forEach((th, index) => {
      // Первая колонка (№) и «Действия» не ресайзятся
      if (index === 0 || th.dataset.colKey === 'actions') return

      const { handle, cleanup } = createResizeHandle(th)
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
