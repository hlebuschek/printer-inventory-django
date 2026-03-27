<template>
  <div
    v-show="isVisible"
    ref="scrollbarRef"
    class="fixed-scrollbar"
    @scroll="onFixedScrollbarScroll"
  >
    <div class="fixed-scrollbar-content" :style="{ width: contentWidth + 'px' }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  targetSelector: {
    type: String,
    required: true
  }
})

const scrollbarRef = ref(null)
const contentWidth = ref(0)
const isVisible = ref(false)
let targetElement = null
let mutationObserver = null
let resizeObserver = null
let parentObserver = null

function syncScrollbarWidth() {
  if (!targetElement) return

  // Проверяем что элемент ещё в DOM (v-if мог его убить)
  if (!targetElement.isConnected) {
    detachFromTarget()
    return
  }

  const table = targetElement.querySelector('table')
  if (table) {
    contentWidth.value = table.scrollWidth
    isVisible.value = table.scrollWidth > targetElement.clientWidth
  } else {
    isVisible.value = false
  }
}

function onTargetScroll() {
  if (!targetElement || !scrollbarRef.value) return
  scrollbarRef.value.scrollLeft = targetElement.scrollLeft
}

function onFixedScrollbarScroll() {
  if (!targetElement || !scrollbarRef.value) return
  targetElement.scrollLeft = scrollbarRef.value.scrollLeft
}

function attachToTarget(el) {
  targetElement = el

  syncScrollbarWidth()

  el.addEventListener('scroll', onTargetScroll)

  // Отслеживаем изменения внутри target (колонки, данные)
  mutationObserver = new MutationObserver(syncScrollbarWidth)
  mutationObserver.observe(el, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'style']
  })

  // Отслеживаем изменения размеров
  resizeObserver = new ResizeObserver(syncScrollbarWidth)
  resizeObserver.observe(el)
  const table = el.querySelector('table')
  if (table) {
    resizeObserver.observe(table)
  }
}

function detachFromTarget() {
  if (targetElement) {
    targetElement.removeEventListener('scroll', onTargetScroll)
    targetElement = null
  }
  if (mutationObserver) {
    mutationObserver.disconnect()
    mutationObserver = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  isVisible.value = false
}

/**
 * Наблюдатель за родителем — ловит момент когда target-элемент
 * появляется или исчезает из DOM (v-if/v-else пересоздаёт его).
 */
function startWatchingForTarget() {
  // Пробуем найти сразу
  const el = document.querySelector(props.targetSelector)
  if (el) {
    attachToTarget(el)
  }

  // Наблюдаем за DOM — если target пересоздан, переподключаемся
  parentObserver = new MutationObserver(() => {
    const currentEl = document.querySelector(props.targetSelector)

    if (currentEl && currentEl !== targetElement) {
      // Новый элемент появился (или пересоздан) — переподключаемся
      detachFromTarget()
      attachToTarget(currentEl)
    } else if (!currentEl && targetElement) {
      // Элемент исчез из DOM
      detachFromTarget()
    }
  })

  parentObserver.observe(document.body, {
    childList: true,
    subtree: true
  })
}

function cleanup() {
  detachFromTarget()
  window.removeEventListener('resize', syncScrollbarWidth)
  if (parentObserver) {
    parentObserver.disconnect()
    parentObserver = null
  }
}

onMounted(() => {
  window.addEventListener('resize', syncScrollbarWidth)
  startWatchingForTarget()
})

onUnmounted(() => {
  cleanup()
})
</script>

<style scoped>
.fixed-scrollbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 17px;
  background: var(--pi-overlay-light, rgba(248, 249, 250, 0.95));
  border-top: 1px solid var(--pi-border-color, rgba(0, 0, 0, 0.1));
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 1000;
  backdrop-filter: blur(3px);
  box-shadow: 0 -2px 8px var(--pi-shadow-light, rgba(0, 0, 0, 0.1));
}

.fixed-scrollbar-content {
  height: 1px;
}

/* Улучшенный стиль скроллбара */
.fixed-scrollbar::-webkit-scrollbar {
  height: 14px;
}

.fixed-scrollbar::-webkit-scrollbar-track {
  background: var(--pi-scrollbar-track, rgba(0, 0, 0, 0.05));
}

.fixed-scrollbar::-webkit-scrollbar-thumb {
  background: var(--pi-scrollbar-thumb, rgba(0, 0, 0, 0.3));
  border-radius: 7px;
  border: 2px solid var(--pi-overlay-light, rgba(248, 249, 250, 0.95));
}

.fixed-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--pi-scrollbar-thumb-hover, rgba(0, 0, 0, 0.5));
}
</style>
