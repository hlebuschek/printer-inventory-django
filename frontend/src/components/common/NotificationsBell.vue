<template>
  <div class="dropdown">
    <button
      ref="toggleButton"
      class="btn btn-link nav-link position-relative px-2"
      type="button"
      data-bs-toggle="dropdown"
      data-bs-auto-close="outside"
      title="Уведомления"
      @click="reload"
    >
      <i class="bi" :class="unreadCount ? 'bi-bell-fill' : 'bi-bell'"></i>
      <span
        v-if="unreadCount"
        class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
      >{{ unreadCount }}</span>
    </button>

    <div class="dropdown-menu dropdown-menu-end shadow" style="min-width: 24rem; max-width: 90vw">
      <div class="d-flex justify-content-between align-items-center px-3 py-2">
        <span class="fw-semibold">{{ history ? 'История уведомлений' : 'Новые уведомления' }}</span>
        <div class="btn-group btn-group-sm">
          <button class="btn btn-link btn-sm text-decoration-none p-0 me-3" @click="toggleHistory">
            {{ history ? 'Только новые' : 'История' }}
          </button>
          <button
            v-if="unreadCount"
            class="btn btn-link btn-sm text-decoration-none p-0"
            @click="markAll"
          >
            Прочитать все
          </button>
        </div>
      </div>
      <div class="dropdown-divider my-0"></div>

      <div v-if="loading" class="px-3 py-3 text-center text-muted small">Загрузка…</div>
      <div v-else-if="!items.length" class="px-3 py-3 text-muted small">
        {{ history ? 'Уведомлений пока не было' : 'Новых уведомлений нет' }}
      </div>

      <div v-else style="max-height: 60vh; overflow-y: auto">
        <div
          v-for="item in items"
          :key="item.id"
          class="d-flex align-items-start gap-2 px-3 py-2 border-bottom"
          :class="{ 'opacity-50': item.read }"
        >
          <a :href="item.url" class="flex-grow-1 text-decoration-none text-body" @click="markRead(item)">
            <span class="d-block fw-semibold small">{{ item.title }}</span>
            <span class="d-block text-muted small text-truncate" style="max-width: 17rem">{{ item.subtitle }}</span>
            <span class="d-block text-muted" style="font-size: 0.75rem">{{ formatDateTime(item.created_at) }}</span>
          </a>
          <button
            v-if="!item.read"
            class="btn btn-sm btn-outline-secondary border-0"
            title="Пометить прочитанным"
            @click="markRead(item)"
          >
            <i class="bi bi-check2"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { fetchApi } from '../../utils/api'

const items = ref([])
const unreadCount = ref(0)
const loading = ref(false)
const history = ref(false)

function formatDateTime(value) {
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

async function reload() {
  loading.value = true
  try {
    const data = await fetchApi(`/api/notifications/${history.value ? '?history=1' : ''}`)
    items.value = data.items
    unreadCount.value = data.unread_count
  } catch (e) {
    items.value = []
  } finally {
    loading.value = false
  }
}

function toggleHistory() {
  history.value = !history.value
  return reload()
}

async function markRead(item) {
  // Помечаем ровно одно: рядом может висеть другое уведомление, которое ещё не читали
  if (item.read) return
  try {
    await fetchApi(`/api/notifications/${item.id}/read/`, { method: 'POST' })
    item.read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    if (!history.value) items.value = items.value.filter((entry) => entry.id !== item.id)
  } catch (e) {
    /* уведомление останется непрочитанным — это безопасно */
  }
}

async function markAll() {
  try {
    await fetchApi('/api/notifications/read-all/', { method: 'POST' })
    await reload()
  } catch (e) {
    /* см. markRead */
  }
}

onMounted(reload)
</script>
