<template>
  <div>
    <ToastContainer />

    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0"><i class="bi bi-journal-text me-2"></i>Журнал заявок подрядчику</h4>
      <div class="d-flex align-items-center gap-3">
        <button
          v-if="permissions.view_all_requests"
          class="btn btn-sm btn-outline-secondary"
          @click="openUnmatched"
        >
          <i class="bi bi-inbox me-1"></i>Письма без заявки
          <span v-if="unmatched.count" class="badge bg-warning text-dark ms-1">{{ unmatched.count }}</span>
        </button>
        <button
          v-if="permissions.view_all_requests && okdeskUnmatched.count"
          class="btn btn-sm btn-outline-secondary"
          @click="openOkdeskUnmatched"
        >
          <i class="bi bi-ticket-detailed me-1"></i>Okdesk без устройства
          <span class="badge bg-warning text-dark ms-1">{{ okdeskUnmatched.count }}</span>
        </button>
        <button
          class="btn btn-sm"
          :class="showAnalytics ? 'btn-primary' : 'btn-outline-primary'"
          @click="showAnalytics = !showAnalytics"
        >
          <i class="bi bi-bar-chart me-1"></i>Аналитика
        </button>
        <button
          v-if="permissions.export_service_requests"
          class="btn btn-sm btn-outline-success"
          title="Выгрузить в Excel заявки с текущими фильтрами"
          :disabled="exporting"
          @click="exportExcel"
        >
          <i class="bi bi-file-earmark-excel me-1"></i>{{ exporting ? 'Формируется…' : 'Экспорт' }}
        </button>
        <a
          v-if="permissions.view_okdesk_archive"
          class="btn btn-sm btn-outline-secondary"
          href="/integrations/okdesk/"
          title="Заявки в Okdesk до появления журнала"
        >
          <i class="bi bi-archive me-1"></i>Архив Okdesk
        </a>
        <span class="text-muted small">Всего: {{ pagination.total_count }}</span>
      </div>
    </div>

    <div class="card mb-3">
      <div class="card-body py-2">
        <div class="row g-2 align-items-end">
          <div class="col-md-3">
            <label class="form-label form-label-sm text-muted mb-0">Поиск</label>
            <input
              v-model="filters.q"
              type="search"
              class="form-control form-control-sm"
              placeholder="Серийник, адрес, организация, акт, инициатор"
              @keyup.enter="reload(1)"
            >
          </div>
          <div class="col-md-2">
            <label class="form-label form-label-sm text-muted mb-0">Статус</label>
            <select v-model="filters.status" class="form-select form-select-sm" @change="reload(1)">
              <option value="active">Незакрытые</option>
              <option value="">Все</option>
              <option value="open">Открыта</option>
              <option value="restored">Ждёт акта</option>
              <option value="closed">Выполнена</option>
              <option value="rejected">Отклонена</option>
            </select>
          </div>
          <div class="col-md-2">
            <label class="form-label form-label-sm text-muted mb-0">С даты</label>
            <input v-model="filters.date_from" type="date" class="form-control form-control-sm" @change="reload(1)">
          </div>
          <div class="col-md-2">
            <label class="form-label form-label-sm text-muted mb-0">По дату</label>
            <input v-model="filters.date_to" type="date" class="form-control form-control-sm" @change="reload(1)">
          </div>
          <div class="col-md-3 d-flex gap-3">
            <div class="form-check">
              <input id="f-overdue" v-model="filters.overdue" class="form-check-input" type="checkbox" @change="reload(1)">
              <label class="form-check-label small" for="f-overdue">Только просроченные</label>
            </div>
            <div v-if="permissions.view_all_requests" class="form-check">
              <input id="f-mine" v-model="filters.mine" class="form-check-input" type="checkbox" @change="reload(1)">
              <label class="form-check-label small" for="f-mine">Только мои</label>
            </div>
          </div>
        </div>
      </div>
    </div>

    <RequestAnalyticsPanel v-if="showAnalytics" :query="appliedQuery" />

    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">Загрузка...</span></div>
    </div>

    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>

    <div v-else-if="!requests.length" class="alert alert-secondary">Заявок по заданным условиям нет.</div>

    <div v-else class="table-responsive">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>Номер</th>
            <th>Оборудование</th>
            <th>Инициатор</th>
            <th>Зарегистрирована</th>
            <th>Норматив</th>
            <th class="text-end">Простой, раб. ч</th>
            <th>Статус</th>
            <th>Переписка</th>
            <th>Акт</th>
            <th v-if="permissions.close_service_request"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in requests" :key="item.id">
            <td>
              <div class="fw-semibold">{{ item.number }}</div>
              <div v-if="item.external_number" class="text-muted small">у подрядчика: {{ item.external_number }}</div>
              <span
                v-if="urgencyBadge(item)"
                class="badge mt-1"
                :class="urgencyBadge(item).cls"
                :title="urgencyBadge(item).title"
              >{{ urgencyBadge(item).label }}</span>
            </td>
            <td>
              <div>{{ item.device.organization }} • {{ item.device.city }}</div>
              <div class="text-muted small">
                {{ item.device.address }}<span v-if="item.device.room">, каб. {{ item.device.room }}</span>
              </div>
              <div class="text-muted small">{{ item.device.model }} • SN: {{ item.device.serial_number || '—' }}</div>
            </td>
            <td class="small">
              <div>{{ item.initiator || '—' }}</div>
              <div class="text-muted">{{ item.service_provider }}</div>
            </td>
            <td class="small">{{ formatDateTime(item.registered_at) }}</td>
            <td class="small">
              <div :class="item.is_overdue ? 'text-danger fw-semibold' : ''">{{ formatDateTime(item.deadline_at) }}</div>
              <div class="text-muted">{{ item.sla_hours }} раб. ч<span v-if="item.is_critical"> • критичный</span></div>
            </td>
            <td class="text-end">
              <span v-if="item.stops_printing">{{ item.downtime_hours }}</span>
              <span v-else class="text-muted">—</span>
              <div v-if="item.restoration_discrepancy_hours !== null" class="text-muted small">
                подрядчик: {{ discrepancyLabel(item) }}
              </div>
            </td>
            <td>
              <span class="badge" :class="statusClass(item)">{{ item.status_display }}</span>
              <div v-if="item.restored_at" class="text-muted small">{{ formatDateTime(item.restored_at) }}</div>
              <div v-if="item.closing_candidate">
                <span
                  class="badge text-bg-warning mt-1"
                  title="Подрядчик прислал письмо с вложением, похожим на акт, но заявка не закрылась — откройте переписку и закройте письмом"
                >возможно, акт</span>
              </div>
            </td>
            <td>
              <button
                class="btn btn-sm btn-link p-0 text-decoration-none"
                :disabled="!item.messages_count"
                @click="openThread(item)"
              >
                <i class="bi bi-envelope me-1"></i>{{ item.messages_count }}
              </button>
            </td>
            <td class="small">
              <a v-if="item.act_url" :href="item.act_url" target="_blank" rel="noopener">
                {{ item.act_number || 'скан' }}
              </a>
              <span v-else class="text-muted">—</span>
              <span
                v-if="item.closing_channel"
                class="badge text-bg-light border ms-1"
                :title="item.closing_channel === 'okdesk'
                  ? 'Акт взят из закрывающего комментария Okdesk'
                  : 'Заявку закрыло письмо подрядчика — проверьте время восстановления'"
              >{{ item.closing_channel === 'okdesk' ? 'из Okdesk' : 'по письму' }}</span>
            </td>
            <td v-if="permissions.close_service_request" class="text-nowrap">
              <button
                v-if="item.status === 'open'"
                class="btn btn-sm btn-outline-success"
                @click="openModal(item, 'restore')"
              >
                Восстановлена
              </button>
              <button
                v-else-if="item.status !== 'rejected'"
                class="btn btn-sm btn-outline-primary"
                @click="openModal(item, 'act')"
              >
                {{ item.act_url ? 'Заменить акт' : 'Акт' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination
      v-if="!loading && requests.length"
      :current-page="pagination.current_page"
      :total-pages="pagination.total_pages"
      :per-page="pagination.per_page"
      :per-page-options="[25, 50, 100, 200]"
      @page-change="reload"
      @per-page-change="changePerPage"
    />

    <!-- Отметка восстановления / приём акта -->
    <div v-if="modal.item" class="modal fade show" style="display: block" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              {{ modal.mode === 'restore' ? 'Восстановление работоспособности' : 'Технический акт' }}
              <span class="text-muted ms-2 small">{{ modal.item.number }}</span>
            </h5>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>

          <div class="modal-body">
            <div v-if="modal.error" class="alert alert-danger py-2">{{ modal.error }}</div>

            <template v-if="modal.mode === 'restore'">
              <div class="mb-3">
                <label class="form-label">Когда печать заработала</label>
                <input v-model="form.restored_at" type="datetime-local" class="form-control">
                <div class="form-text">С этого момента простой в показателе K1 не идёт.</div>
              </div>

              <hr>
              <p class="text-muted small mb-2">
                Данные подрядчика — по п. 6.5.2 ТЗ фактическое время фиксирует Исполнитель.
                Заполняются, если его цифры расходятся с нашими.
              </p>
              <div class="mb-3">
                <label class="form-label">Восстановлено по данным подрядчика</label>
                <input v-model="form.provider_restored_at" type="datetime-local" class="form-control">
              </div>
              <div class="mb-0">
                <label class="form-label">Простой по данным подрядчика, рабочих часов</label>
                <input v-model="form.provider_downtime_hours" type="number" step="0.01" min="0" class="form-control">
              </div>
            </template>

            <template v-else>
              <div class="mb-3">
                <label class="form-label">Номер акта</label>
                <input v-model="form.act_number" type="text" class="form-control" maxlength="64">
              </div>
              <div class="mb-3">
                <label class="form-label">Дата акта</label>
                <input v-model="form.closed_at" type="datetime-local" class="form-control">
              </div>
              <div class="mb-0">
                <label class="form-label">Скан акта</label>
                <input ref="actFileInput" type="file" class="form-control" accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.heic,.heif">
                <div class="form-text">
                  Без скана запрос не считается выполненным (п. 6.6.4 ТЗ). PDF или фото, до 10 МБ.
                </div>
              </div>
            </template>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="closeModal">Отмена</button>
            <button type="button" class="btn btn-primary" :disabled="modal.saving" @click="submit">
              <span v-if="modal.saving" class="spinner-border spinner-border-sm me-1"></span>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="modal.item" class="modal-backdrop fade show"></div>

    <!-- Лента переписки по заявке -->
    <div v-if="thread.item" class="modal fade show d-block" tabindex="-1">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              Переписка<span class="text-muted ms-2 small">{{ thread.item.number }}</span>
            </h5>
            <button
              type="button"
              class="btn btn-sm ms-auto me-2"
              :class="thread.item.subscribed ? 'btn-primary' : 'btn-outline-secondary'"
              :disabled="thread.subscribing"
              @click="toggleSubscription"
            >
              <i class="bi me-1" :class="thread.item.subscribed ? 'bi-bell-fill' : 'bi-bell'"></i>
              {{ thread.item.subscribed ? 'Слежу' : 'Следить' }}
            </button>
            <button type="button" class="btn-close" @click="closeThread"></button>
          </div>

          <div class="modal-body">
            <div v-if="thread.loading" class="text-center py-4">
              <div class="spinner-border text-primary" role="status"></div>
            </div>
            <div v-else-if="thread.error" class="alert alert-danger py-2">{{ thread.error }}</div>
            <template v-else>
              <div v-for="message in thread.messages" :key="message.id">
                <MessageCard :message="message" />
                <div v-if="canCloseByMessage(message)" class="text-end mb-3">
                  <button
                    class="btn btn-sm btn-outline-success"
                    :disabled="thread.closingId === message.id"
                    title="Вложение письма станет сканом акта, заявка будет выполнена"
                    @click="closeByMessage(message)"
                  >
                    <span v-if="thread.closingId === message.id" class="spinner-border spinner-border-sm me-1"></span>
                    <i v-else class="bi bi-check2-circle me-1"></i>Закрыть заявку этим письмом
                  </button>
                </div>
              </div>
            </template>

            <div v-if="!thread.loading" class="border-top pt-3">
              <div v-if="thread.replyError" class="alert alert-danger py-2">{{ thread.replyError }}</div>
              <div v-if="isEmailThread" class="row g-2 mb-2">
                <div class="col-md-6">
                  <label class="form-label small text-muted mb-0">Кому</label>
                  <select v-model="thread.replyTo" class="form-select form-select-sm">
                    <option value="">Автоматически (последний ответивший)</option>
                    <option v-for="address in thread.replyOptions" :key="address" :value="address">
                      {{ address }}
                    </option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label small text-muted mb-0">В копию — коллеги из системы</label>
                  <select v-model="thread.replyCc" class="form-select form-select-sm" multiple size="3">
                    <option v-for="colleague in colleagues" :key="colleague.email" :value="colleague.email">
                      {{ colleague.name }} ({{ colleague.email }})
                    </option>
                  </select>
                </div>
              </div>
              <textarea
                v-model="thread.replyText"
                class="form-control mb-2"
                rows="3"
                :placeholder="isEmailThread ? 'Ответ подрядчику' : 'Комментарий в Okdesk'"
              ></textarea>
              <input v-if="isEmailThread" ref="replyFilesInput" type="file" class="form-control form-control-sm" multiple>
              <div v-if="isEmailThread" class="form-text">
                Уйдёт в ту же переписку, ответ вернётся сюда же. Файл — до 20 МБ.
                Несколько коллег в копию — через Ctrl/Cmd.
              </div>
              <div v-else class="form-text">
                Уйдёт комментарием в Okdesk от вашего имени — нужен личный API-токен
                (меню пользователя → Токен Okdesk). Ответ подрядчика появится здесь после синхронизации.
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="thread.sending"
              @click="sendReply"
            >
              {{ thread.sending ? 'Отправка…' : 'Отправить' }}
            </button>
            <button type="button" class="btn btn-secondary" @click="closeThread">Закрыть</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="thread.item" class="modal-backdrop fade show"></div>

    <!-- Письма, в которых не нашлось номера заявки -->
    <div v-if="unmatched.open" class="modal fade show d-block" tabindex="-1">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Письма без заявки</h5>
            <button type="button" class="btn-close" @click="unmatched.open = false"></button>
          </div>

          <div class="modal-body">
            <p class="text-muted small">
              В теме этих писем не нашлось номера заявки. Укажите номер, чтобы письмо встало в её ленту.
            </p>

            <div v-if="unmatched.loading" class="text-center py-4">
              <div class="spinner-border text-primary" role="status"></div>
            </div>
            <div v-else-if="!unmatched.messages.length" class="alert alert-secondary py-2 mb-0">
              Непривязанных писем нет.
            </div>

            <div v-for="message in unmatched.messages" v-else :key="message.id">
              <MessageCard :message="message" />
              <div v-if="permissions.close_service_request" class="d-flex gap-2 mb-3">
                <input
                  v-model="unmatched.numbers[message.id]"
                  type="text"
                  class="form-control form-control-sm"
                  placeholder="Номер заявки, например 2026-00001"
                >
                <button class="btn btn-sm btn-primary text-nowrap" @click="attachMessage(message)">Привязать</button>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="unmatched.open = false">Закрыть</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="unmatched.open" class="modal-backdrop fade show"></div>

    <div v-if="okdeskUnmatched.open" class="modal fade show d-block" tabindex="-1">
      <div class="modal-dialog modal-xl modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Заявки Okdesk без устройства в договоре</h5>
            <button type="button" class="btn-close" @click="okdeskUnmatched.open = false"></button>
          </div>

          <div class="modal-body">
            <p class="text-muted small">
              Эти открытые заявки не попадают в журнал: их серийник не нашёлся среди устройств договора.
              Лечится исправлением серийника в договоре или в заявке Okdesk — привязка подтянется синхронизацией.
              Если серийника в заявке нет вовсе, устройство выбирается вручную кнопкой «В журнал».
            </p>

            <div v-if="okdeskUnmatched.loading" class="text-center py-4">
              <div class="spinner-border text-primary" role="status"></div>
            </div>
            <div v-else-if="!okdeskUnmatched.issues.length" class="alert alert-secondary py-2 mb-0">
              Все открытые заявки Okdesk привязаны к устройствам.
            </div>

            <table v-else class="table table-sm align-middle">
              <thead>
                <tr>
                  <th>№ в Okdesk</th>
                  <th>Заголовок</th>
                  <th>Серийники</th>
                  <th>Компания</th>
                  <th>Статус</th>
                  <th>Создана</th>
                  <th v-if="permissions.close_service_request"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="issue in okdeskUnmatched.issues" :key="issue.issue_id">
                  <td>
                    <a :href="issue.url" target="_blank" rel="noopener">{{ issue.issue_id }}</a>
                  </td>
                  <td class="small">{{ issue.title }}</td>
                  <td class="small font-monospace">{{ issue.serial_numbers || '—' }}</td>
                  <td class="small">{{ issue.company || '—' }}</td>
                  <td class="small">{{ issue.status }}</td>
                  <td class="small text-nowrap">{{ formatDateTime(issue.created_at) }}</td>
                  <td v-if="permissions.close_service_request" class="text-end">
                    <button
                      class="btn btn-sm btn-outline-primary"
                      :class="{ active: okdeskLink.issue?.issue_id === issue.issue_id }"
                      @click="startOkdeskLink(issue)"
                    >
                      В журнал
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div v-if="okdeskLink.issue" class="card">
              <div class="card-body py-2">
                <div class="small fw-semibold mb-2">
                  Okdesk {{ okdeskLink.issue.issue_id }} — выберите устройство
                </div>
                <div v-if="okdeskLink.error" class="alert alert-warning py-1 small mb-2">{{ okdeskLink.error }}</div>
                <div class="row g-2 align-items-start">
                  <div class="col-md-7">
                    <template v-if="!okdeskLink.device">
                      <input
                        v-model="okdeskLink.q"
                        type="search"
                        class="form-control form-control-sm"
                        placeholder="Серийник, адрес, организация, город"
                        @input="queueOkdeskDeviceSearch"
                      >
                      <div v-if="okdeskLink.searching" class="form-text">Поиск…</div>
                      <div
                        v-else-if="okdeskLink.options.length"
                        ref="okdeskOptionsEl"
                        class="list-group mt-1 shadow-sm"
                        style="max-height: 260px; overflow-y: auto;"
                      >
                        <button
                          v-for="device in okdeskLink.options"
                          :key="device.id"
                          type="button"
                          class="list-group-item list-group-item-action py-1 small"
                          @click="selectOkdeskDevice(device)"
                        >
                          <span class="font-monospace">{{ device.serial_number || 'б/с' }}</span> · {{ device.model }}
                          <div class="text-body-secondary">
                            {{ device.organization }}<template v-if="device.city"> · {{ device.city }}</template>
                            <template v-if="device.address"> · {{ device.address }}</template>
                          </div>
                        </button>
                      </div>
                    </template>
                    <div v-else class="d-flex align-items-center gap-2 small border rounded px-2 py-1">
                      <span class="text-truncate">
                        <span class="font-monospace">{{ okdeskLink.device.serial_number || 'б/с' }}</span>
                        · {{ okdeskLink.device.model }} · {{ okdeskLink.device.organization }}
                        <template v-if="okdeskLink.device.city">({{ okdeskLink.device.city }})</template>
                      </span>
                      <button
                        type="button"
                        class="btn-close ms-auto"
                        style="font-size: 0.6rem;"
                        title="Сменить устройство"
                        @click="clearOkdeskDevice"
                      ></button>
                    </div>
                  </div>
                  <div class="col-auto">
                    <button
                      class="btn btn-sm btn-primary"
                      :disabled="!okdeskLink.device || okdeskLink.saving"
                      @click="importOkdeskIssue"
                    >
                      {{ okdeskLink.saving ? 'Завожу…' : 'Завести заявку' }}
                    </button>
                  </div>
                </div>
                <div class="form-text">
                  Заявка появится в журнале со своим номером и датой из Okdesk, комментарии подтянутся синхронизацией.
                  Привязка в самом Okdesk не меняется.
                </div>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="okdeskUnmatched.open = false">Закрыть</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="okdeskUnmatched.open" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import MessageCard from './MessageCard.vue'
import RequestAnalyticsPanel from './RequestAnalyticsPanel.vue'
import Pagination from '../common/Pagination.vue'
import ToastContainer from '../common/ToastContainer.vue'
import { useToast } from '../../composables/useToast'
import { fetchApi } from '../../utils/api'

const props = defineProps({
  permissions: { type: Object, default: () => ({}) }
})

const { showToast } = useToast()

const requests = ref([])
const loading = ref(true)
const error = ref('')
const actFileInput = ref(null)
const showAnalytics = ref(false)
// Снимок применённых фильтров, общий для таблицы, аналитики и выгрузки: поиск
// применяется по Enter, и до него на экране остаётся прежняя выборка
const appliedQuery = ref('')
const exporting = ref(false)
const replyFilesInput = ref(null)

const filters = reactive({
  q: '',
  status: 'active',
  date_from: '',
  date_to: '',
  overdue: false,
  mine: false
})

const pagination = reactive({
  total_count: 0,
  total_pages: 1,
  current_page: 1,
  per_page: 50
})

const thread = reactive({
  item: null,
  loading: false,
  messages: [],
  error: '',
  replyText: '',
  replyError: '',
  replyTo: '',
  replyCc: [],
  replyOptions: [],
  sending: false,
  subscribing: false,
  closingId: null
})
// Пустой канал (заявка ещё грузится) считаем почтовым: форма всё равно скрыта до загрузки
const isEmailThread = computed(() => (thread.item?.channel || 'email') === 'email')
const colleagues = ref([])
const unmatched = reactive({ open: false, loading: false, messages: [], numbers: {}, count: 0 })
const okdeskUnmatched = reactive({ open: false, loading: false, issues: [], count: 0 })
const okdeskLink = reactive({ issue: null, q: '', options: [], device: null, searching: false, saving: false, error: '' })
const okdeskOptionsEl = ref(null)

const modal = reactive({ item: null, mode: 'restore', saving: false, error: '' })
const form = reactive({
  restored_at: '',
  provider_restored_at: '',
  provider_downtime_hours: '',
  act_number: '',
  closed_at: ''
})

function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function discrepancyLabel(item) {
  const hours = item.restoration_discrepancy_hours
  const sign = hours > 0 ? 'раньше нас на ' : 'позже нас на '
  return `${sign}${Math.abs(hours)} ч`
}

function urgencyBadge(item) {
  if (item.is_critical) {
    return { label: 'Критичная', cls: 'text-bg-danger', title: 'Печать остановлена, норматив 4 рабочих часа. Учитывается в K1 и K2' }
  }
  if (!item.stops_printing && !item.counts_in_sla) {
    return { label: 'Плановая', cls: 'text-bg-light border', title: 'Картридж в резерв: не учитывается ни в K1, ни в K2' }
  }
  if (!item.stops_printing) {
    return { label: 'Печать работает', cls: 'text-bg-secondary', title: 'Простой не идёт в K1, но заявка учитывается в K2' }
  }
  return { label: 'Обычная', cls: 'text-bg-warning', title: 'Печать остановлена, норматив по городу. Учитывается в K1 и K2' }
}

function statusClass(item) {
  if (item.status === 'closed') return 'bg-success'
  if (item.status === 'rejected') return 'bg-secondary'
  if (item.is_overdue) return 'bg-danger'
  return item.status === 'restored' ? 'bg-info text-dark' : 'bg-warning text-dark'
}

/** datetime-local отдаёт локальное время без зоны — сервер трактует его как время сервера. */
function nowForInput() {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 16)
}

function filterParams() {
  const params = new URLSearchParams({ status: filters.status, q: filters.q })
  if (filters.overdue) params.set('overdue', '1')
  if (filters.mine) params.set('mine', '1')
  if (filters.date_from) params.set('date_from', `${filters.date_from}T00:00`)
  if (filters.date_to) params.set('date_to', `${filters.date_to}T23:59`)
  return params
}

const EXPORT_POLL_MS = 1500
const EXPORT_TIMEOUT_MS = 10 * 60 * 1000

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    // Именно applied, а не текущее содержимое полей: поиск применяется по Enter,
    // и набранный, но не применённый текст не должен попасть в выгрузку
    const { download_url } = await fetchApi(`/contracts/api/requests/export/?${appliedQuery.value}`)
    showToast('Формируется файл', 'Выгрузка готовится в фоне, подождите', 'info')

    const deadline = Date.now() + EXPORT_TIMEOUT_MS
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, EXPORT_POLL_MS))
      const resp = await fetch(download_url)
      if (resp.status === 202) continue
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      // Скачиваем через blob, а не переходом по ссылке: файл лежит в кэше
      // и отдаётся только владельцу выгрузки
      const href = URL.createObjectURL(await resp.blob())
      const link = document.createElement('a')
      link.href = href
      link.download = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'requests.xlsx'
      document.body.appendChild(link)
      link.click()
      link.remove()
      // Освобождать сразу нельзя: браузер к этому моменту ещё не прочитал blob
      setTimeout(() => URL.revokeObjectURL(href), 60_000)
      return
    }
    throw new Error('Файл не успел сформироваться')
  } catch (e) {
    showToast('Ошибка', `Не удалось выгрузить журнал: ${e.message}`, 'error')
  } finally {
    exporting.value = false
  }
}

async function reload(page = 1) {
  loading.value = true
  error.value = ''

  const params = filterParams()
  appliedQuery.value = params.toString()
  params.set('page', page)
  params.set('per_page', pagination.per_page)

  try {
    const data = await fetchApi(`/contracts/api/requests/?${params}`)
    requests.value = data.requests
    Object.assign(pagination, data.pagination)
  } catch (e) {
    error.value = 'Не удалось загрузить журнал заявок'
  } finally {
    loading.value = false
  }
}

function changePerPage(value) {
  pagination.per_page = value
  reload(1)
}

async function openThread(item) {
  thread.item = item
  thread.messages = []
  thread.error = ''
  thread.replyText = ''
  thread.replyError = ''
  thread.replyTo = ''
  thread.replyCc = []
  thread.replyOptions = []
  thread.loading = true
  loadColleagues()

  try {
    const data = await fetchApi(`/contracts/api/requests/${item.id}/messages/`)
    thread.messages = data.messages
    thread.replyOptions = data.reply_options || []
    Object.assign(thread.item, data.request)
  } catch (e) {
    thread.error = 'Не удалось загрузить переписку'
  } finally {
    thread.loading = false
  }
}

let colleaguesLoaded = false
async function loadColleagues() {
  if (colleaguesLoaded) return
  colleaguesLoaded = true
  try {
    const data = await fetchApi('/contracts/api/requests/colleagues/')
    colleagues.value = data.colleagues
  } catch (e) {
    colleagues.value = []
  }
}

function closeThread() {
  thread.item = null
}

function canCloseByMessage(message) {
  return (
    props.permissions.close_service_request &&
    message.has_act_attachment &&
    thread.item &&
    thread.item.status !== 'closed' &&
    thread.item.status !== 'rejected'
  )
}

async function closeByMessage(message) {
  if (!window.confirm(`Закрыть заявку ${thread.item.number} этим письмом? Вложение станет сканом акта.`)) return
  thread.closingId = message.id

  try {
    const data = await fetchApi(
      `/contracts/api/requests/${thread.item.id}/close-by-message/${message.id}/`,
      { method: 'POST', body: new FormData() }
    )
    Object.assign(thread.item, data.request)
    const index = requests.value.findIndex((item) => item.id === data.request.id)
    if (index !== -1) requests.value[index] = data.request
    showToast('Заявка закрыта', `${data.request.number}: акт из письма принят`, 'success')
  } catch (e) {
    const payload = await e.response?.json().catch(() => null)
    showToast('Не удалось закрыть', payload?.error || 'Ошибка закрытия по письму', 'danger')
  } finally {
    thread.closingId = null
  }
}

function openRequestFromQuery() {
  // Ссылка из уведомления: заявки может не быть на текущей странице журнала,
  // поэтому хватает id — остальное приедет вместе с перепиской
  const id = Number(new URLSearchParams(window.location.search).get('request'))
  if (!id) return
  openThread(requests.value.find((item) => item.id === id) || { id })
}

async function toggleSubscription() {
  thread.subscribing = true
  const on = !thread.item.subscribed

  const body = new FormData()
  body.append('on', on ? '1' : '0')

  try {
    const data = await fetchApi(`/contracts/api/requests/${thread.item.id}/subscribe/`, { method: 'POST', body })
    thread.item.subscribed = data.subscribed
  } catch (e) {
    showToast('Не удалось изменить подписку', `Заявка ${thread.item.number}`, 'danger')
  } finally {
    thread.subscribing = false
  }
}

async function sendReply() {
  const files = isEmailThread.value ? Array.from(replyFilesInput.value?.files || []) : []
  const text = thread.replyText.trim()
  if (!text && !files.length) {
    thread.replyError = isEmailThread.value
      ? 'Письмо без текста и вложений отправлять нечего.'
      : 'Комментарий не может быть пустым.'
    return
  }

  thread.sending = true
  thread.replyError = ''

  const body = new FormData()
  body.append('text', text)
  if (isEmailThread.value && thread.replyTo) body.append('to', thread.replyTo)
  if (isEmailThread.value) thread.replyCc.forEach((email) => body.append('cc', email))
  files.forEach((file) => body.append('attachments', file))

  try {
    const data = await fetchApi(`/contracts/api/requests/${thread.item.id}/reply/`, { method: 'POST', body })
    thread.messages.push(data.message)
    thread.replyText = ''
    thread.replyCc = []
    if (replyFilesInput.value) replyFilesInput.value.value = ''
    const index = requests.value.findIndex((item) => item.id === thread.item.id)
    if (index !== -1) requests.value[index].messages_count += 1
    showToast('Отправлено', `Ответ по заявке ${thread.item.number} ушёл подрядчику`, 'success')
  } catch (e) {
    const payload = await e.response?.json().catch(() => null)
    thread.replyError = payload?.error || 'Не удалось отправить письмо'
  } finally {
    thread.sending = false
  }
}

async function loadUnmatched() {
  unmatched.loading = true
  try {
    const data = await fetchApi('/contracts/api/requests/messages/unmatched/')
    unmatched.messages = data.messages
    unmatched.count = data.messages.length
  } catch (e) {
    unmatched.messages = []
  } finally {
    unmatched.loading = false
  }
}

function openUnmatched() {
  unmatched.open = true
  loadUnmatched()
}

async function loadOkdeskUnmatched() {
  okdeskUnmatched.loading = true
  try {
    const data = await fetchApi('/contracts/api/requests/okdesk/unmatched/')
    okdeskUnmatched.issues = data.issues
    okdeskUnmatched.count = data.issues.length
  } catch (e) {
    okdeskUnmatched.issues = []
  } finally {
    okdeskUnmatched.loading = false
  }
}

function openOkdeskUnmatched() {
  okdeskUnmatched.open = true
  okdeskLink.issue = null
  loadOkdeskUnmatched()
}

function startOkdeskLink(issue) {
  okdeskLink.issue = issue
  okdeskLink.q = issue.serial_numbers || ''
  okdeskLink.options = []
  okdeskLink.device = null
  okdeskLink.error = ''
  if (okdeskLink.q.trim().length >= 2) searchOkdeskDevice(true)
}

let okdeskSearchTimer = null

function queueOkdeskDeviceSearch() {
  okdeskLink.error = ''
  clearTimeout(okdeskSearchTimer)
  if (okdeskLink.q.trim().length < 2) {
    okdeskLink.options = []
    return
  }
  okdeskSearchTimer = setTimeout(searchOkdeskDevice, 300)
}

async function searchOkdeskDevice(autoSelect = false) {
  const q = okdeskLink.q.trim()
  okdeskLink.searching = true
  okdeskLink.error = ''
  try {
    const data = await fetchApi(`/contracts/api/requests/okdesk/device-search/?q=${encodeURIComponent(q)}`)
    if (q !== okdeskLink.q.trim()) return
    okdeskLink.options = data.devices
    if (autoSelect && data.devices.length === 1) selectOkdeskDevice(data.devices[0])
    if (!data.devices.length) okdeskLink.error = 'Ничего не нашлось — уточните серийник, адрес, организацию или город.'
    // список в потоке модалки — докручиваем modal-body, чтобы он был виден
    await nextTick()
    okdeskOptionsEl.value?.scrollIntoView({ block: 'nearest' })
  } catch (e) {
    okdeskLink.options = []
    okdeskLink.error = 'Поиск устройств не удался.'
  } finally {
    okdeskLink.searching = false
  }
}

function selectOkdeskDevice(device) {
  okdeskLink.device = device
  okdeskLink.options = []
}

function clearOkdeskDevice() {
  okdeskLink.device = null
  if (okdeskLink.q.trim().length >= 2) searchOkdeskDevice()
}

async function importOkdeskIssue() {
  okdeskLink.saving = true
  okdeskLink.error = ''

  const body = new FormData()
  body.append('device_id', okdeskLink.device.id)

  try {
    const data = await fetchApi(`/contracts/api/requests/okdesk/${okdeskLink.issue.issue_id}/import/`, {
      method: 'POST',
      body
    })
    showToast('Заявка в журнале', `Okdesk ${okdeskLink.issue.issue_id} → ${data.request.number}`, 'success')
    okdeskLink.issue = null
    loadOkdeskUnmatched()
    reload(pagination.current_page)
  } catch (e) {
    const payload = await e.response?.json().catch(() => null)
    okdeskLink.error = payload?.error || 'Не удалось завести заявку.'
  } finally {
    okdeskLink.saving = false
  }
}

async function attachMessage(message) {
  const number = (unmatched.numbers[message.id] || '').trim()
  if (!number) return

  const body = new FormData()
  body.append('number', number)

  try {
    const result = await fetchApi(`/contracts/api/requests/messages/${message.id}/attach/`, { method: 'POST', body })
    const note = result?.closed_by_letter ? `Заявка ${number} закрыта по письму` : `Заявка ${number}`
    showToast('Письмо привязано', note, 'success')
    delete unmatched.numbers[message.id]
    await Promise.all([loadUnmatched(), reload(pagination.current_page)])
  } catch (e) {
    const payload = await e.response?.json().catch(() => null)
    showToast('Не удалось привязать', payload?.error || 'Ошибка привязки письма', 'danger')
  }
}

function openModal(item, mode) {
  modal.item = item
  modal.mode = mode
  modal.error = ''
  form.restored_at = nowForInput()
  form.provider_restored_at = ''
  form.provider_downtime_hours = ''
  form.act_number = item.act_number || ''
  form.closed_at = nowForInput()
}

function closeModal() {
  modal.item = null
}

async function submit() {
  modal.saving = true
  modal.error = ''

  const body = new FormData()
  let url

  if (modal.mode === 'restore') {
    url = `/contracts/api/requests/${modal.item.id}/restore/`
    body.append('restored_at', form.restored_at)
    if (form.provider_restored_at) body.append('provider_restored_at', form.provider_restored_at)
    if (form.provider_downtime_hours) body.append('provider_downtime_hours', form.provider_downtime_hours)
  } else {
    url = `/contracts/api/requests/${modal.item.id}/act/`
    body.append('act_number', form.act_number)
    body.append('closed_at', form.closed_at)
    const file = actFileInput.value?.files?.[0]
    if (file) body.append('act_scan', file)
  }

  try {
    const data = await fetchApi(url, { method: 'POST', body })
    const index = requests.value.findIndex((item) => item.id === data.request.id)
    if (index !== -1) requests.value[index] = data.request
    showToast('Сохранено', `Заявка ${data.request.number}: ${data.request.status_display.toLowerCase()}`, 'success')
    closeModal()
  } catch (e) {
    const payload = await e.response?.json().catch(() => null)
    modal.error = payload?.error || 'Не удалось сохранить изменения'
  } finally {
    modal.saving = false
  }
}

onMounted(() => {
  reload(1).then(openRequestFromQuery)
  if (props.permissions.view_all_requests) {
    loadUnmatched()
    loadOkdeskUnmatched()
  }
})
</script>
