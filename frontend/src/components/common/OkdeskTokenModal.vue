<template>
  <div v-if="show" class="modal fade show" style="display: block" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title"><i class="bi bi-key me-2"></i>Токены Okdesk</h5>
          <button type="button" class="btn-close" @click="close"></button>
        </div>
        <div class="modal-body">
          <p class="text-muted" style="font-size: 0.85rem;">
            Личный API-токен из Okdesk — свой для каждого подрядчика. Нужен для отправки заявок и комментариев.
          </p>

          <div v-if="loading" class="text-center py-3">
            <span class="spinner-border spinner-border-sm"></span>
          </div>

          <div v-else-if="!instances.length" class="alert alert-warning py-1 px-2 mb-0" style="font-size: 0.85rem;">
            Нет активных инстансов Okdesk. Обратитесь к администратору.
          </div>

          <div v-else>
            <div v-for="inst in instances" :key="inst.id" class="border rounded p-2 mb-2">
              <div class="d-flex align-items-center justify-content-between mb-2">
                <strong style="font-size: 0.9rem;">{{ inst.provider_name }}</strong>
                <span v-if="inst.has_token" class="badge bg-success">токен задан</span>
                <span v-else class="badge bg-secondary">нет токена</span>
              </div>
              <div class="input-group input-group-sm">
                <input type="password" class="form-control" v-model="tokens[inst.id]"
                       :placeholder="inst.has_token ? 'Новый токен (заменит текущий)' : 'API-токен'"
                       @keyup.enter="save(inst)">
                <button class="btn btn-primary" :disabled="!(tokens[inst.id] || '').trim() || saving[inst.id]"
                        @click="save(inst)">
                  <span v-if="saving[inst.id]" class="spinner-border spinner-border-sm"></span>
                  <span v-else>Сохранить</span>
                </button>
                <button v-if="inst.has_token" class="btn btn-outline-danger" :disabled="saving[inst.id]"
                        title="Удалить токен" @click="remove(inst)">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
          </div>

          <div v-if="message" class="alert alert-success mt-2 py-1 px-2 mb-0" style="font-size: 0.85rem;">
            {{ message }}
          </div>
          <div v-if="error" class="alert alert-danger mt-2 py-1 px-2 mb-0" style="font-size: 0.85rem;">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm" @click="close">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="show" class="modal-backdrop fade show"></div>
</template>

<script>
function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content
    || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''
}

export default {
  name: 'OkdeskTokenModal',
  data() {
    return {
      show: false,
      loading: false,
      instances: [],
      tokens: {},
      saving: {},
      message: '',
      error: '',
    }
  },
  mounted() {
    window.openOkdeskModal = () => this.open()
  },
  beforeUnmount() {
    delete window.openOkdeskModal
  },
  methods: {
    async open() {
      this.tokens = {}
      this.saving = {}
      this.message = ''
      this.error = ''
      this.show = true
      await this.load()
    },
    close() {
      this.show = false
    },
    async load() {
      this.loading = true
      try {
        const resp = await fetch('/api/okdesk-token/')
        const data = await resp.json()
        this.instances = data.ok ? (data.instances || []) : []
        if (!data.ok) this.error = data.error || 'Ошибка загрузки'
      } catch {
        this.error = 'Ошибка сети'
      } finally {
        this.loading = false
      }
    },
    async save(inst) {
      const token = (this.tokens[inst.id] || '').trim()
      if (!token) return
      this.saving = { ...this.saving, [inst.id]: true }
      this.message = ''
      this.error = ''
      try {
        const resp = await fetch('/api/okdesk-token/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ instance_id: inst.id, token }),
        })
        const data = await resp.json()
        if (data.ok) {
          this.message = `Токен для «${inst.provider_name}» сохранён`
          this.tokens = { ...this.tokens, [inst.id]: '' }
          inst.has_token = true
        } else {
          this.error = data.error || 'Ошибка'
        }
      } catch {
        this.error = 'Ошибка сети'
      } finally {
        this.saving = { ...this.saving, [inst.id]: false }
      }
    },
    async remove(inst) {
      this.saving = { ...this.saving, [inst.id]: true }
      this.message = ''
      this.error = ''
      try {
        const resp = await fetch('/api/okdesk-token/', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ instance_id: inst.id }),
        })
        const data = await resp.json()
        if (data.ok) {
          this.message = `Токен для «${inst.provider_name}» удалён`
          inst.has_token = false
        } else {
          this.error = data.error || 'Ошибка'
        }
      } catch {
        this.error = 'Ошибка сети'
      } finally {
        this.saving = { ...this.saving, [inst.id]: false }
      }
    },
  },
}
</script>
