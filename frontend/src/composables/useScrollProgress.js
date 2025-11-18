import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable для отслеживания прогресса горизонтального скролла
 * @param {Ref} containerRef - Ref на скроллируемый контейнер
 */
export function useScrollProgress(containerRef) {
  const scrollProgress = ref(0)
  const isScrollable = ref(false)

  /**
   * Обновление прогресса скролла
   */
  const updateProgress = () => {
    if (!containerRef.value) return

    const container = containerRef.value
    const scrollWidth = container.scrollWidth
    const clientWidth = container.clientWidth
    const scrollLeft = container.scrollLeft

    // Проверяем, нужен ли скролл
    isScrollable.value = scrollWidth > clientWidth

    if (!isScrollable.value) {
      scrollProgress.value = 0
      return
    }

    // Вычисляем прогресс (0-100%)
    const maxScroll = scrollWidth - clientWidth
    const progress = maxScroll > 0 ? (scrollLeft / maxScroll) * 100 : 0
    scrollProgress.value = Math.min(100, Math.max(0, progress))
  }

  /**
   * Обработчик изменения размера
   */
  const handleResize = () => {
    updateProgress()
  }

  onMounted(() => {
    if (!containerRef.value) return

    // Добавляем обработчики событий
    containerRef.value.addEventListener('scroll', updateProgress)
    window.addEventListener('resize', handleResize)

    // Наблюдаем за изменениями размера контейнера
    const resizeObserver = new ResizeObserver(updateProgress)
    resizeObserver.observe(containerRef.value)

    // Первоначальное обновление
    setTimeout(updateProgress, 100)
  })

  onUnmounted(() => {
    if (containerRef.value) {
      containerRef.value.removeEventListener('scroll', updateProgress)
    }
    window.removeEventListener('resize', handleResize)
  })

  return {
    scrollProgress,
    isScrollable,
    updateProgress
  }
}
