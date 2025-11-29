<template>
  <div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 1055;">
    <transition-group name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast show"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
      >
        <div class="toast-header">
          <i :class="getIconClass(toast.type)" class="me-2"></i>
          <strong class="me-auto">{{ toast.title }}</strong>
          <small class="text-muted">сейчас</small>
          <button
            type="button"
            class="btn-close"
            @click="hideToast(toast.id)"
            aria-label="Close"
          ></button>
        </div>
        <div class="toast-body">
          {{ toast.message }}
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToast } from '@/composables/useToast'

const { toasts, hideToast } = useToast()

function getIconClass(type) {
  const icons = {
    success: 'bi bi-check-circle text-success',
    error: 'bi bi-x-circle text-danger',
    warning: 'bi bi-exclamation-triangle text-warning',
    info: 'bi bi-info-circle text-info'
  }
  return icons[type] || icons.info
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast {
  animation: slideInRight 0.3s ease-out;
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
