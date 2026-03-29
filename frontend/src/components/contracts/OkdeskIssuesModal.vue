  <template>
    <div v-if="show" class="modal fade show" style="display: block" tabindex="-1">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-ticket-detailed me-2"></i>Заявки Okdesk
              <span v-if="deviceSerial" class="text-muted ms-2" style="font-size: 0.85rem;">
                SN: {{ deviceSerial }}
              </span>
            </h5>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>

          <div class="modal-body">
            <!-- Загрузка -->
            <div v-if="loading" class="text-center py-5">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
              </div>
            </div>

            <!-- Ошибка -->
            <div v-else-if="error" class="alert alert-danger" role="alert">
              <strong>Ошибка:</strong> {{ error }}
            </div>

            <template v-else>
              <!-- Форма создания заявки -->
              <div v-if="canCreate" class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center py-2"
                     style="cursor: pointer;" @click="showCreateForm = !showCreateForm">
                  <span class="fw-bold">
                    <i class="bi bi-plus-circle me-1"></i> Создать заявку
                  </span>
                  <i class="bi" :class="showCreateForm ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                </div>

                <div v-if="showCreateForm" class="card-body">
                  <!-- Нет токена -->
                  <div v-if="!hasOkdeskToken" class="alert alert-warning mb-0">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    API-токен Okdesk не настроен. Добавьте его в меню пользователя
                    <strong>→ Токен Okdesk</strong>.
                  </div>

                  <template v-else>
                    <!-- Автозаполненные поля (read-only) -->
                    <div class="row g-2 mb-3">
                      <div class="col-md-4">
                        <label class="form-label form-label-sm text-muted mb-0">Организация</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.organization" readonly>
                      </div>
                      <div class="col-md-2">
                        <label class="form-label form-label-sm text-muted mb-0">Город</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.city" readonly>
                      </div>
                      <div class="col-md-4">
                        <label class="form-label form-label-sm text-muted mb-0">Адрес</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.address" readonly>
                      </div>
                      <div class="col-md-2">
                        <label class="form-label form-label-sm text-muted mb-0">Кабинет</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.room_number" readonly>
                      </div>
                    </div>

                    <div class="row g-2 mb-3">
                      <div class="col-md-3">
                        <label class="form-label form-label-sm text-muted mb-0">Производитель</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.manufacturer" readonly>
                      </div>
                      <div class="col-md-3">
                        <label class="form-label form-label-sm text-muted mb-0">Модель</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.model" readonly>
                      </div>
                      <div class="col-md-3">
                        <label class="form-label form-label-sm text-muted mb-0">Серийный номер</label>
                        <input type="text" class="form-control form-control-sm" :value="deviceInfo.serial_number" readonly>
                      </div>
                      <div class="col-md-3">
                        <label class="form-label form-label-sm text-muted mb-0">Ремонт/обслуживание</label>
                        <select class="form-select form-select-sm" v-model="createForm.service_type">
                          <option value="Обслуживание">Обслуживание</option>
                          <option value="Ремонт">Ремонт</option>
                          <option value="Диагностика">Диагностика</option>
                          <option value="Заказ картриджа">Заказ картриджа</option>
                        </select>
                      </div>
                    </div>

                    <!-- Редактируемые поля -->
                    <div class="row g-2 mb-3">
                      <div class="col-md-6">
                        <label class="form-label form-label-sm text-muted mb-0">Картридж</label>
                        <textarea class="form-control form-control-sm" rows="2"
                                  v-model="createForm.cartridge"
                                  placeholder="Картриджи..."></textarea>
                      </div>
                      <div class="col-md-6">
                        <label class="form-label form-label-sm text-muted mb-0">Комментарии</label>
                        <textarea class="form-control form-control-sm" rows="2"
                                  v-model="createForm.comment"
                                  placeholder="Описание проблемы..."></textarea>
                      </div>
                    </div>

                    <!-- Подпись -->
                    <div class="border-top pt-3 mt-2 mb-3">
                      <div class="text-muted mb-1" style="font-size: 0.8rem;">Подпись к заявке</div>
                      <div class="d-flex align-items-start gap-2">
                        <div class="text-nowrap pt-1" style="font-size: 0.9rem;">
                          С уважением, <strong>{{ userFullName }}</strong>
                        </div>
                        <div class="flex-grow-1" style="max-width: 300px;">
                          <input type="text" class="form-control form-control-sm"
                                 v-model="createForm.phone"
                                 placeholder="Телефон для обратной связи">
                        </div>
                      </div>
                    </div>

                    <!-- Результат отправки -->
                    <div v-if="createSuccess" class="alert alert-success py-2 mb-2">
                      <i class="bi bi-check-circle me-1"></i>
                      Заявка <strong>#{{ createdIssueId }}</strong> создана
                    </div>
                    <div v-if="createError" class="alert alert-danger py-2 mb-2">
                      <i class="bi bi-exclamation-circle me-1"></i> {{ createError }}
                    </div>

                    <div class="d-flex gap-2">
                      <button class="btn btn-primary btn-sm" :disabled="creating" @click="submitIssue">
                        <span v-if="creating" class="spinner-border spinner-border-sm me-1"></span>
                        <i v-else class="bi bi-send me-1"></i>
                        {{ canRetry ? 'Повторить отправку' : 'Отправить в Okdesk' }}
                      </button>
                    </div>
                  </template>
                </div>
              </div>

              <!-- Таблица заявок -->
              <div v-if="issues.length">
                <div class="mb-2 text-muted" style="font-size: 0.85rem;">
                  Найдено заявок: {{ issues.length }}
                </div>
                <div class="table-responsive" style="max-height: 50vh; overflow-y: auto;">
                  <table class="table table-sm table-striped table-hover table-bordered align-middle mb-0">
                    <thead class="table-light sticky-top">
                      <tr>
                        <th style="width: 80px;">№</th>
                        <th style="width: 120px;">Дата</th>
                        <th>Заголовок</th>
                        <th style="width: 140px;">Статус</th>
                        <th style="width: 120px;">Приоритет</th>
                        <th style="width: 180px;">Исполнитель</th>
                        <th style="width: 120px;">Закрыта</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="issue in issues" :key="issue.id">
                        <td>
                          <span class="text-primary fw-bold">{{ issue.id }}</span>
                        </td>
                        <td>{{ formatDate(issue.created_at) }}</td>
                        <td>
                          {{ issue.title }}
                          <span v-if="issue.is_overdue" class="badge bg-danger ms-1" title="Просрочена">
                            <i class="bi bi-exclamation-triangle"></i>
                          </span>
                        </td>
                        <td>
                          <span class="badge" :class="statusBadgeClass(issue.status_name)">
                            {{ issue.status_name || '—' }}
                          </span>
                        </td>
                        <td>{{ issue.priority_name || '—' }}</td>
                        <td>{{ issue.assignee_name || '—' }}</td>
                        <td>{{ formatDate(issue.completed_at) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div v-else-if="!showCreateForm" class="text-center py-4 text-muted">
                <i class="bi bi-check-circle" style="font-size: 2rem;"></i>
                <p class="mt-2">Заявок по этому устройству не найдено</p>
              </div>
            </template>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="closeModal">
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="show" class="modal-backdrop fade show"></div>
  </template>

  <script>
  export default {
    name: 'OkdeskIssuesModal',
    props: {
      show: {
        type: Boolean,
        default: false
      },
      deviceId: {
        type: Number,
        default: null
      },
      deviceSerial: {
        type: String,
        default: ''
      },
      canCreate: {
        type: Boolean,
        default: false
      }
    },
    data() {
      return {
        loading: false,
        error: null,
        issues: [],
        hasOkdeskToken: false,
        deviceInfo: {},
        userFullName: '',
        showCreateForm: false,
        creating: false,
        createError: null,
        createSuccess: false,
        createdIssueId: null,
        canRetry: false,
        createForm: {
          cartridge: '',
          service_type: 'Обслуживание',
          comment: '',
          phone: '',
        }
      }
    },
    watch: {
      show(newVal) {
        if (newVal && this.deviceId) {
          this.fetchIssues()
        } else if (!newVal) {
          this.showCreateForm = false
          this.createSuccess = false
          this.createError = null
        }
      }
    },
    methods: {
      async fetchIssues() {
        this.loading = true
        this.error = null
        this.issues = []
        this.createSuccess = false
        this.createError = null

        try {
          const response = await fetch(`/integrations/okdesk/issues/${this.deviceId}/`)
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`)
          }
          const data = await response.json()
          if (!data.ok) {
            throw new Error(data.error || 'Неизвестная ошибка')
          }
          this.issues = data.issues || []
          this.hasOkdeskToken = data.has_okdesk_token || false
          this.deviceInfo = data.device_info || {}
          this.userFullName = data.user_full_name || ''

          // Автозаполняем поля формы
          this.createForm.cartridge = this.deviceInfo.cartridge || ''
          this.createForm.comment = ''
          this.createForm.service_type = 'Обслуживание'
          this.createForm.phone = data.user_phone || ''
        } catch (err) {
          console.error('Error fetching Okdesk issues:', err)
          this.error = err.message || 'Не удалось загрузить заявки'
        } finally {
          this.loading = false
        }
      },

      async submitIssue() {
        this.creating = true
        this.createError = null
        this.createSuccess = false
        this.canRetry = false

        try {
          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''

          const response = await fetch('/integrations/okdesk/create-issue/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
              device_id: this.deviceId,
              cartridge: this.createForm.cartridge,
              service_type: this.createForm.service_type,
              comment: this.createForm.comment,
              phone: this.createForm.phone,
            }),
          })

          const data = await response.json()

          if (!data.ok) {
            this.canRetry = !!data.retry
            throw new Error(data.error || 'Ошибка создания заявки')
          }

          this.createSuccess = true
          this.createdIssueId = data.issue_id

          // Перезагрузить список заявок чтобы новая отобразилась
          await this.fetchIssues()
          this.createSuccess = true
          this.createdIssueId = data.issue_id

        } catch (err) {
          console.error('Error creating Okdesk issue:', err)
          this.createError = err.message || 'Не удалось создать заявку'
          if (!this.canRetry && err.message?.includes('сет')) {
            this.canRetry = true
          }
        } finally {
          this.creating = false
        }
      },

      closeModal() {
        this.$emit('close')
      },

      formatDate(isoString) {
        if (!isoString) return '—'
        const date = new Date(isoString)
        return date.toLocaleDateString('ru-RU', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        })
      },

      statusBadgeClass(status) {
        const map = {
          'Закрыта': 'bg-secondary',
          'Открыта': 'bg-success',
          'В работе': 'bg-primary',
          'Ожидает запчасть': 'bg-warning text-dark',
          'Заявка собрана': 'bg-info text-dark',
          'Отправлено в сторонний сервис': 'bg-info text-dark',
        }
        return map[status] || 'bg-secondary'
      }
    }
  }
  </script>

  <style scoped>
  .modal-xl {
    max-width: 1140px;
  }

  .sticky-top {
    z-index: 1;
  }

  .card-header {
    user-select: none;
  }
  </style>
