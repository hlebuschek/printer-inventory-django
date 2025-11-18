<template>
  <div
    v-if="isVisible"
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
const targetElement = ref(null)
let mutationObserver = null

function syncScrollbarWidth() {
  if (!targetElement.value) return

  const table = targetElement.value.querySelector('table')
  if (table) {
    contentWidth.value = table.scrollWidth

    // Show scrollbar only if content is wider than container
    isVisible.value = table.scrollWidth > targetElement.value.clientWidth
  }
}

function onTargetScroll() {
  if (!targetElement.value || !scrollbarRef.value) return
  scrollbarRef.value.scrollLeft = targetElement.value.scrollLeft
}

function onFixedScrollbarScroll() {
  if (!targetElement.value || !scrollbarRef.value) return
  targetElement.value.scrollLeft = scrollbarRef.value.scrollLeft
}

function init() {
  targetElement.value = document.querySelector(props.targetSelector)

  if (!targetElement.value) {
    console.warn(`FixedScrollbar: target element "${props.targetSelector}" not found`)
    return
  }

  // Initial sync
  syncScrollbarWidth()

  // Sync on target scroll
  targetElement.value.addEventListener('scroll', onTargetScroll)

  // Sync on window resize
  window.addEventListener('resize', syncScrollbarWidth)

  // Watch for DOM changes (column visibility, etc.)
  mutationObserver = new MutationObserver(syncScrollbarWidth)
  mutationObserver.observe(targetElement.value, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'style']
  })
}

function cleanup() {
  if (targetElement.value) {
    targetElement.value.removeEventListener('scroll', onTargetScroll)
  }

  window.removeEventListener('resize', syncScrollbarWidth)

  if (mutationObserver) {
    mutationObserver.disconnect()
    mutationObserver = null
  }
}

onMounted(() => {
  // Use setTimeout to ensure target element is rendered
  setTimeout(init, 100)
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
  background: rgba(248, 249, 250, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 1000;
  backdrop-filter: blur(3px);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.fixed-scrollbar-content {
  height: 1px;
}

/* Улучшенный стиль скроллбара */
.fixed-scrollbar::-webkit-scrollbar {
  height: 14px;
}

.fixed-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
}

.fixed-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 7px;
  border: 2px solid rgba(248, 249, 250, 0.95);
}

.fixed-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.5);
}
</style>
