<template>
  <div v-if="show" class="modal fade show" style="display: block" tabindex="-1">
    <div class="modal-dialog modal-xl">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            <i class="bi bi-clock-history me-2"></i>История изменений
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

          <!-- Пустая история -->
          <div v-else-if="!history || history.length === 0" class="text-center py-5 text-muted">
            <p>История изменений пуста</p>
          </div>

          <!-- История -->
          <div v-else class="timeline">
            <div
              v-for="(log, index) in history"
              :key="log.id"
              class="timeline-item mb-4"
              :class="getActionClass(log.action)"
            >
              <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                  <div>
                    <span class="badge" :class="getActionBadgeClass(log.action)">
                      <i :class="getActionIcon(log.action)"></i> {{ log.action_display }}
                    </span>
                    <strong class="ms-2">{{ log.user }}</strong>
                  </div>
                  <small class="text-muted">
                    {{ formatDateTime(log.timestamp) }}
                    <span v-if="log.ip_address" class="ms-2">
                      <i class="bi bi-globe"></i> {{ log.ip_address }}
                    </span>
                  </small>
                </div>

                <div v-if="log.changes && log.changes.length > 0" class="card-body">
                  <table class="table table-sm table-borderless mb-0">
                    <thead>
                      <tr>
                        <th style="width: 30%">Поле</th>
                        <th style="width: 35%">Старое значение</th>
                        <th style="width: 35%">Новое значение</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(change, idx) in log.changes" :key="idx">
                        <td class="fw-bold">{{ change.label }}</td>
                        <td>
                          <span class="text-muted" v-if="change.old === '—'">—</span>
                          <code v-else class="bg-light px-2 py-1 rounded">{{ change.old }}</code>
                        </td>
                        <td>
                          <span class="text-muted" v-if="change.new === '—'">—</span>
                          <code v-else class="bg-success bg-opacity-10 px-2 py-1 rounded text-success">
                            {{ change.new }}
                          </code>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div v-else class="card-body">
                  <p class="text-muted mb-0">Нет подробностей изменений</p>
                </div>
              </div>
            </div>
          </div>
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
  name: 'ChangeHistoryModal',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    historyUrl: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      loading: false,
      error: null,
      history: []
    };
  },
  watch: {
    show(newVal) {
      if (newVal) {
        this.fetchHistory();
      }
    }
  },
  methods: {
    async fetchHistory() {
      this.loading = true;
      this.error = null;

      try {
        const response = await fetch(this.historyUrl);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        this.history = data.history || [];
      } catch (err) {
        console.error('Error fetching history:', err);
        this.error = err.message || 'Не удалось загрузить историю';
      } finally {
        this.loading = false;
      }
    },

    closeModal() {
      this.$emit('close');
    },

    getActionClass(action) {
      const classes = {
        create: 'timeline-item-create',
        update: 'timeline-item-update',
        delete: 'timeline-item-delete'
      };
      return classes[action] || '';
    },

    getActionBadgeClass(action) {
      const classes = {
        create: 'bg-success',
        update: 'bg-primary',
        delete: 'bg-danger'
      };
      return classes[action] || 'bg-secondary';
    },

    getActionIcon(action) {
      const icons = {
        create: 'bi bi-plus-circle',
        update: 'bi bi-pencil',
        delete: 'bi bi-trash'
      };
      return icons[action] || 'bi bi-file-text';
    },

    formatDateTime(isoString) {
      if (!isoString) return '';

      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      // Относительное время для недавних изменений
      if (diffMins < 1) return 'только что';
      if (diffMins < 60) return `${diffMins} мин. назад`;
      if (diffHours < 24) return `${diffHours} ч. назад`;
      if (diffDays < 7) return `${diffDays} дн. назад`;

      // Полная дата для старых изменений
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  }
};
</script>

<style scoped>
.timeline {
  position: relative;
}

.timeline-item {
  position: relative;
  padding-left: 40px;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: -30px;
  width: 2px;
  background: #dee2e6;
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-item-create::after {
  content: '\f4fe'; /* Bootstrap icon bi-plus-circle */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #198754;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

.timeline-item-update::after {
  content: '\f4ca'; /* Bootstrap icon bi-pencil */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #0d6efd;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

.timeline-item-delete::after {
  content: '\f5de'; /* Bootstrap icon bi-trash */
  font-family: 'bootstrap-icons';
  position: absolute;
  left: 5px;
  top: 10px;
  width: 24px;
  height: 24px;
  background: #dc3545;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 2px solid white;
}

.modal-xl {
  max-width: 1140px;
}

code {
  font-size: 0.875em;
}

.table th {
  font-weight: 600;
  color: #6c757d;
  border-bottom: 2px solid #dee2e6;
}
</style>
