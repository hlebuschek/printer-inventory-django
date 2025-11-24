import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable для создания плавающего горизонтального скроллбара
 * @param {Ref} containerRef - Ref на скроллируемый контейнер (.table-responsive)
 */
export function useFloatingScrollbar(containerRef) {
  const floatingScrollbar = ref(null)
  const floatingContent = ref(null)
  const isVisible = ref(false)

  let syncTimeout = null

  /**
   * Синхронизация скролла от таблицы к плавающему скроллу
   */
  const syncFromContainer = () => {
    if (!containerRef.value || !floatingScrollbar.value) return

    clearTimeout(syncTimeout)
    syncTimeout = setTimeout(() => {
      floatingScrollbar.value.scrollLeft = containerRef.value.scrollLeft
    }, 10)
  }

  /**
   * Синхронизация скролла от плавающего скролла к таблице
   */
  const syncToContainer = () => {
    if (!containerRef.value || !floatingScrollbar.value) return

    clearTimeout(syncTimeout)
    syncTimeout = setTimeout(() => {
      containerRef.value.scrollLeft = floatingScrollbar.value.scrollLeft
    }, 10)
  }

  /**
   * Обновление размера и видимости плавающего скроллбара
   */
  const updateScrollbar = () => {
    if (!containerRef.value || !floatingContent.value) return

    const container = containerRef.value
    const needsScroll = container.scrollWidth > container.clientWidth

    isVisible.value = needsScroll

    if (needsScroll) {
      // Устанавливаем ширину контента скроллбара равной scrollWidth таблицы
      floatingContent.value.style.width = `${container.scrollWidth}px`

      // Синхронизируем начальную позицию
      floatingScrollbar.value.scrollLeft = container.scrollLeft
    }
  }

  /**
   * Проверка, виден ли плавающий скроллбар в viewport
   */
  const shouldShowFloating = () => {
    if (!containerRef.value) return false

    const containerRect = containerRef.value.getBoundingClientRect()
    const viewportHeight = window.innerHeight

    // Показываем плавающий скролл, если нижняя граница таблицы ниже viewport
    return containerRect.bottom > viewportHeight
  }

  /**
   * Обработчик скролла страницы
   */
  const handlePageScroll = () => {
    if (!floatingScrollbar.value) return

    const shouldShow = shouldShowFloating() && isVisible.value
    floatingScrollbar.value.style.opacity = shouldShow ? '1' : '0'
    floatingScrollbar.value.style.pointerEvents = shouldShow ? 'auto' : 'none'
  }

  /**
   * Инициализация плавающего скроллбара
   */
  const init = () => {
    // Создаем элементы плавающего скроллбара
    const scrollbarDiv = document.createElement('div')
    scrollbarDiv.className = 'floating-scrollbar'
    scrollbarDiv.style.cssText = `
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 20px;
      overflow-x: auto;
      overflow-y: hidden;
      z-index: 1000;
      background: rgba(255, 255, 255, 0.95);
      border-top: 1px solid #dee2e6;
      box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
      transition: opacity 0.2s ease;
      opacity: 0;
      pointer-events: none;
    `

    const contentDiv = document.createElement('div')
    contentDiv.style.cssText = `
      height: 1px;
      pointer-events: none;
    `

    scrollbarDiv.appendChild(contentDiv)
    document.body.appendChild(scrollbarDiv)

    floatingScrollbar.value = scrollbarDiv
    floatingContent.value = contentDiv

    // Добавляем обработчики событий
    containerRef.value?.addEventListener('scroll', syncFromContainer)
    scrollbarDiv.addEventListener('scroll', syncToContainer)
    window.addEventListener('scroll', handlePageScroll)
    window.addEventListener('resize', updateScrollbar)

    // Наблюдаем за изменениями размера контейнера
    const resizeObserver = new ResizeObserver(updateScrollbar)
    if (containerRef.value) {
      resizeObserver.observe(containerRef.value)
    }

    // Первоначальное обновление
    updateScrollbar()
    handlePageScroll()

    return () => {
      containerRef.value?.removeEventListener('scroll', syncFromContainer)
      scrollbarDiv.removeEventListener('scroll', syncToContainer)
      window.removeEventListener('scroll', handlePageScroll)
      window.removeEventListener('resize', updateScrollbar)
      resizeObserver.disconnect()
      scrollbarDiv.remove()
    }
  }

  onMounted(() => {
    // Небольшая задержка для гарантии, что DOM готов
    setTimeout(init, 100)
  })

  onUnmounted(() => {
    if (floatingScrollbar.value) {
      floatingScrollbar.value.remove()
    }
  })

  return {
    isVisible,
    updateScrollbar
  }
}
