<template>
  <div v-if="show" class="modal fade show" style="display: block" tabindex="-1">
    <div class="modal-dialog modal-sm">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title"><i class="bi bi-key me-2"></i>Токен Okdesk</h5>
          <button type="button" class="btn-close" @click="close"></button>
        </div>
        <div class="modal-body">
          <p class="text-muted" style="font-size: 0.85rem;">
            Введите ваш API-токен из Okdesk для отправки заявок.
          </p>
          <input type="password" class="form-control" v-model="token" placeholder="API-токен"
                 @keyup.enter="save">
          <div v-if="message" class="alert alert-success mt-2 py-1 px-2 mb-0" style="font-size: 0.85rem;">
            {{ message }}
          </div>
          <div v-if="error" class="alert alert-danger mt-2 py-1 px-2 mb-0" style="font-size: 0.85rem;">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm" @click="close">Закрыть</button>
          <button type="button" class="btn btn-primary btn-sm" :disabled="!token.trim() || saving" @click="save">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            Сохранить
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="show" class="modal-backdrop fade show"></div>
</template>

<script>
export default {
  name: 'OkdeskTokenModal',
  data() {
    return {
      show: false,
      token: '',
      saving: false,
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
    open() {
      this.token = ''
      this.message = ''
      this.error = ''
      this.saving = false
      this.show = true
    },
    close() {
      this.show = false
    },
    async save() {
      if (!this.token.trim()) return
      this.saving = true
      this.message = ''
      this.error = ''

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
          || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''

        const resp = await fetch('/api/okdesk-token/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({ token: this.token }),
        })
        const data = await resp.json()

        if (data.ok) {
          this.message = 'Токен сохранён'
          this.token = ''
        } else {
          this.error = data.error || 'Ошибка'
        }
      } catch {
        this.error = 'Ошибка сети'
      } finally {
        this.saving = false
      }
    },
  },
}
</script>
