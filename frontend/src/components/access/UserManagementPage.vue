<template>
  <div class="user-management-page">
    <div class="d-flex align-items-center justify-content-between mb-3">
      <h1 class="h4 mb-0">
        <i class="bi bi-people me-2"></i>Пользователи
      </h1>
      <button class="btn btn-primary btn-sm" @click="startCreate">
        <i class="bi bi-plus-lg me-1"></i>Добавить
      </button>
    </div>

    <div v-if="error" class="alert alert-danger alert-dismissible">
      {{ error }}
      <button type="button" class="btn-close" @click="error = ''"></button>
    </div>
    <div v-if="notice" class="alert alert-success alert-dismissible">
      {{ notice }}
      <button type="button" class="btn-close" @click="notice = ''"></button>
    </div>

    <div class="row g-3">
      <div class="col-lg-5">
        <div class="card h-100">
          <div class="card-header p-2">
            <input
              v-model="search"
              type="search"
              class="form-control form-control-sm"
              placeholder="Поиск по логину или ФИО"
            >
          </div>
          <div class="card-body p-0">
            <div v-if="loading" class="text-center text-muted py-4">
              <span class="spinner-border spinner-border-sm me-2"></span>Загрузка…
            </div>
            <div v-else-if="!filteredUsers.length" class="text-center text-muted py-4 small">
              Ничего не найдено
            </div>
            <div v-else class="list-group list-group-flush user-list">
              <button
                v-for="user in filteredUsers"
                :key="user.id"
                type="button"
                class="list-group-item list-group-item-action"
                :class="{ active: form.id === user.id }"
                @click="startEdit(user)"
              >
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <div class="min-w-0">
                    <div class="fw-semibold text-truncate">{{ user.username }}</div>
                    <div class="small text-truncate" :class="form.id === user.id ? '' : 'text-muted'">
                      {{ user.full_name || '—' }}
                    </div>
                  </div>
                  <div class="text-end flex-shrink-0">
                    <span v-if="!user.is_active" class="badge text-bg-danger">Отключен</span>
                    <span v-else-if="!user.has_django_user" class="badge text-bg-secondary">Не заходил</span>
                    <span v-else class="badge text-bg-success">Активен</span>
                    <div class="small mt-1" :class="form.id === user.id ? '' : 'text-muted'">
                      {{ user.group_ids.length }} гр.
                    </div>
                  </div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="col-lg-7">
        <div v-if="!formOpen" class="card h-100">
          <div class="card-body d-flex align-items-center justify-content-center text-muted small">
            Выберите пользователя слева или добавьте нового
          </div>
        </div>

        <form v-else class="card h-100" @submit.prevent="save">
          <div class="card-header py-2 fw-semibold">
            {{ form.id ? `Редактирование: ${form.username}` : 'Новый пользователь' }}
          </div>
          <div class="card-body">
            <div class="row g-2 mb-3">
              <div class="col-md-6">
                <label class="form-label small mb-1">Логин (как в Keycloak) <span class="text-danger">*</span></label>
                <input
                  v-model="form.username"
                  type="text"
                  class="form-control form-control-sm"
                  :disabled="form.has_django_user"
                  required
                >
                <div v-if="form.has_django_user" class="form-text small">
                  Пользователь уже заходил — логин менять нельзя
                </div>
              </div>
              <div class="col-md-6">
                <label class="form-label small mb-1">ФИО</label>
                <input v-model="form.full_name" type="text" class="form-control form-control-sm">
              </div>
              <div class="col-md-6">
                <label class="form-label small mb-1">Email</label>
                <input v-model="form.email" type="email" class="form-control form-control-sm">
              </div>
              <div class="col-md-6">
                <label class="form-label small mb-1">Примечание</label>
                <input v-model="form.notes" type="text" class="form-control form-control-sm">
              </div>
            </div>

            <div class="form-check form-switch mb-3">
              <input
                id="user-active"
                v-model="form.is_active"
                class="form-check-input"
                type="checkbox"
                :disabled="isSelf"
              >
              <label class="form-check-label small" for="user-active">
                Доступ разрешён
                <span v-if="isSelf" class="text-muted">(нельзя отключить себя)</span>
              </label>
            </div>

            <div class="d-flex align-items-center justify-content-between mb-2">
              <div class="fw-semibold small">Группы прав</div>
              <button
                v-if="form.group_ids.length"
                type="button"
                class="btn btn-link btn-sm p-0"
                @click="form.group_ids = []"
              >
                Снять все
              </button>
            </div>
            <div v-if="!form.has_django_user" class="alert alert-info py-2 small">
              <i class="bi bi-info-circle me-1"></i>
              Django-пользователя ещё нет. Выбранные группы выдадутся при первом входе через Keycloak.
            </div>

            <div class="groups-box border rounded p-2">
              <div v-for="category in groupCategories" :key="category.name" class="mb-2">
                <div class="text-uppercase text-muted fw-semibold group-category">{{ category.name }}</div>
                <div class="row g-1">
                  <div v-for="group in category.groups" :key="group.id" class="col-md-6">
                    <div class="form-check">
                      <input
                        :id="`group-${group.id}`"
                        v-model="form.group_ids"
                        class="form-check-input"
                        type="checkbox"
                        :value="group.id"
                      >
                      <label class="form-check-label small" :for="`group-${group.id}`">{{ group.title }}</label>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer d-flex gap-2">
            <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              Сохранить
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm" @click="closeForm">Отмена</button>
            <button
              v-if="form.id && !isSelf"
              type="button"
              class="btn btn-outline-danger btn-sm ms-auto"
              :disabled="saving"
              @click="remove"
            >
              <i class="bi bi-trash me-1"></i>Удалить из списка
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchApi } from '../../utils/api.js'

const props = defineProps({
  initialData: {
    type: Object,
    default: () => ({})
  }
})

const catalog = props.initialData.groups || []
const currentUsername = props.initialData.currentUsername || ''

const users = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const search = ref('')
const formOpen = ref(false)

const emptyForm = () => ({
  id: null,
  username: '',
  full_name: '',
  email: '',
  notes: '',
  is_active: true,
  group_ids: [],
  has_django_user: false
})

const form = ref(emptyForm())

const isSelf = computed(
  () => !!form.value.username && form.value.username.toLowerCase() === currentUsername.toLowerCase()
)

const groupCategories = computed(() => {
  const byCategory = new Map()
  for (const group of catalog) {
    if (!byCategory.has(group.category)) byCategory.set(group.category, [])
    byCategory.get(group.category).push(group)
  }
  return [...byCategory].map(([name, groups]) => ({ name, groups }))
})

const filteredUsers = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return users.value
  return users.value.filter(
    (u) => u.username.toLowerCase().includes(query) || (u.full_name || '').toLowerCase().includes(query)
  )
})

async function load() {
  loading.value = true
  try {
    const data = await fetchApi('/api/users/')
    users.value = data.users
  } catch (e) {
    error.value = 'Не удалось загрузить список пользователей'
  } finally {
    loading.value = false
  }
}

function startCreate() {
  form.value = emptyForm()
  formOpen.value = true
}

function startEdit(user) {
  form.value = { ...user, group_ids: [...user.group_ids] }
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  form.value = emptyForm()
}

async function request(url, body) {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    return await fetchApi(url, { method: 'POST', body })
  } catch (e) {
    const detail = await e.response?.json().catch(() => null)
    error.value = detail?.error || 'Ошибка сохранения'
    return null
  } finally {
    saving.value = false
  }
}

async function save() {
  const result = await request('/api/users/save/', {
    id: form.value.id,
    username: form.value.username,
    full_name: form.value.full_name,
    email: form.value.email,
    notes: form.value.notes,
    is_active: form.value.is_active,
    group_ids: form.value.group_ids
  })
  if (!result) return

  notice.value = `Пользователь «${result.user.username}» сохранён`
  await load()
  startEdit(result.user)
}

async function remove() {
  if (!window.confirm(`Удалить «${form.value.username}» из списка доступа? Пользователь будет отключён.`)) return

  const result = await request('/api/users/delete/', { id: form.value.id })
  if (!result) return

  notice.value = 'Пользователь удалён из списка доступа'
  closeForm()
  await load()
}

onMounted(load)
</script>

<style scoped>
.user-list {
  max-height: 60vh;
  overflow-y: auto;
}

.groups-box {
  max-height: 40vh;
  overflow-y: auto;
}

.group-category {
  font-size: 0.7rem;
  letter-spacing: 0.03em;
}

.min-w-0 {
  min-width: 0;
}
</style>
