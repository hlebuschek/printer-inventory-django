<template>
  <div class="web-parser-container">
    <!-- Header -->
    <div class="parser-header">
      <div>
        <h1>Настройка веб-парсинга</h1>
        <div class="printer-info">
          Принтер: {{ printerIp }} (ID: {{ printerId }})
        </div>
      </div>
      <div>
        <a :href="returnUrl" class="btn btn-secondary">
          <i class="bi bi-arrow-left"></i> Назад к списку
        </a>
      </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
      <!-- Left Panel: Configuration & Preview -->
      <div class="panel">
        <h2>Веб-интерфейс принтера</h2>

        <!-- URL Configuration -->
        <div class="form-row">
          <label>Протокол</label>
          <select v-model="config.protocol" class="form-select">
            <option value="http">HTTP</option>
            <option value="https">HTTPS</option>
          </select>
        </div>

        <div class="form-row">
          <label>Путь</label>
          <input
            v-model="config.urlPath"
            type="text"
            class="form-control"
            placeholder="/"
          />
        </div>

        <!-- Auth -->
        <div class="form-row-auth">
          <input
            v-model="config.username"
            type="text"
            class="form-control"
            placeholder="Логин (опционально)"
          />
          <input
            v-model="config.password"
            type="password"
            class="form-control"
            placeholder="Пароль (опционально)"
          />
        </div>

        <!-- Load Page Button -->
        <div class="button-group">
          <button
            class="btn btn-primary"
            :disabled="isLoadingPage"
            @click="loadPrinterPage"
          >
            <span v-if="isLoadingPage" class="spinner-border spinner-border-sm me-2"></span>
            <i v-else class="bi bi-download me-1"></i>
            {{ isLoadingPage ? 'Загрузка...' : 'Загрузить страницу' }}
          </button>
          <button
            v-if="currentUrl"
            class="btn btn-secondary"
            @click="openInNewTab"
          >
            <i class="bi bi-box-arrow-up-right me-1"></i>
            Открыть в новой вкладке
          </button>
          <button
            v-if="finalUrl"
            class="btn btn-outline-secondary"
            @click="copyFinalUrl"
          >
            <i class="bi bi-clipboard me-1"></i>
            Копировать URL
          </button>
        </div>

        <!-- Preview -->
        <div class="preview-container">
          <div v-if="!currentHtml" class="placeholder">
            Нажмите "Загрузить страницу" чтобы увидеть предпросмотр
          </div>
          <div v-else-if="isLoadingIframe" class="placeholder">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Загрузка...</span>
            </div>
            <p class="mt-3">Загрузка страницы...</p>
            <small>Ожидание выполнения JavaScript</small>
          </div>
          <iframe
            v-show="currentHtml && !isLoadingIframe"
            id="webFrame"
            ref="iframeRef"
            :src="proxyUrl"
            frameborder="0"
            @load="onIframeLoad"
          ></iframe>
        </div>

        <!-- Hint -->
        <div class="info-box">
          <strong>Как получить XPath:</strong>
          <p style="font-size: 13px; line-height: 1.6; margin-top: 5px;">
            1. Нажмите "Загрузить страницу" - она появится выше<br>
            2. Откройте DevTools (F12) прямо здесь<br>
            3. Кликните на iframe и найдите нужный элемент<br>
            4. Правой кнопкой → Copy → Copy XPath<br>
            5. Вставьте в конструктор действий<br>
            <strong>Альтернатива:</strong> Используйте кнопку "Открыть в новой вкладке"
          </p>
        </div>

        <!-- XPath Testing -->
        <div class="info-box warning">
          <strong>Тестирование XPath</strong>
          <div class="form-group">
            <label for="testXpath">XPath выражение</label>
            <input
              id="testXpath"
              v-model="testXpathValue"
              type="text"
              class="form-control"
              placeholder="//td[contains(text(),'Serial')]/following-sibling::td/text()"
            />
          </div>
          <div class="form-group">
            <label for="testRegex">Regex паттерн (опционально)</label>
            <input
              id="testRegex"
              v-model="testRegexValue"
              type="text"
              class="form-control"
              placeholder="(\w+)"
            />
          </div>
          <button class="btn btn-warning" @click="testXpath">
            Тестировать
          </button>
          <div v-if="testResult" class="test-result mt-2">
            <strong>Результат:</strong> {{ testResult }}
          </div>
        </div>
      </div>

      <!-- Right Panel: Rule Editor & List -->
      <div class="panel">
        <h2>Правила парсинга</h2>

        <!-- Field Selector -->
        <div class="form-group">
          <label>Поле для обновления</label>
          <select v-model="ruleEditor.fieldName" class="form-select" @change="updateFieldDescription">
            <option value="">— выберите поле —</option>
            <optgroup label="Счетчики">
              <option value="counter">Общий счетчик</option>
              <option value="counter_a4_bw">Счетчик A4 ЧБ</option>
              <option value="counter_a3_bw">Счетчик A3 ЧБ</option>
              <option value="counter_a4_color">Счетчик A4 Цвет</option>
              <option value="counter_a3_color">Счетчик A3 Цвет</option>
            </optgroup>
            <optgroup label="Информация устройства">
              <option value="serial_number">Серийный номер</option>
              <option value="mac_address">MAC-адрес</option>
            </optgroup>
            <optgroup label="Уровни тонера">
              <option value="toner_black">Тонер черный (%)</option>
              <option value="toner_cyan">Тонер голубой (%)</option>
              <option value="toner_magenta">Тонер пурпурный (%)</option>
              <option value="toner_yellow">Тонер желтый (%)</option>
            </optgroup>
            <optgroup label="Барабаны">
              <option value="drum_black">Барабан черный (%)</option>
              <option value="drum_cyan">Барабан голубой (%)</option>
              <option value="drum_magenta">Барабан пурпурный (%)</option>
              <option value="drum_yellow">Барабан желтый (%)</option>
            </optgroup>
          </select>
        </div>

        <!-- Calculated Mode Toggle -->
        <div class="checkbox-group">
          <input
            id="isCalculated"
            v-model="ruleEditor.isCalculated"
            type="checkbox"
            @change="toggleCalculatedMode"
          />
          <label for="isCalculated">Вычисляемое поле (использовать результаты других правил)</label>
        </div>

        <!-- Normal Rule Block -->
        <div v-if="!ruleEditor.isCalculated" id="normalRuleBlock">
          <div class="info-box warning">
            <strong>Инструкция:</strong>
            <p style="font-size: 13px; margin-top: 5px;">
              1. Загрузите страницу принтера<br>
              2. Откройте конструктор действий<br>
              3. Добавьте клики/ожидания/парсинг<br>
              4. Выполните и проверьте результат<br>
              5. Сохраните действия и правило
            </p>
          </div>

          <div class="advanced-options">
            <div class="info-box">
              <strong>Конструктор действий</strong>
              <p style="font-size: 13px; margin-top: 5px;">
                Если данные в другой вкладке/разделе - постройте цепочку действий
              </p>
            </div>

            <button
              type="button"
              class="btn btn-info"
              style="margin-bottom: 15px;"
              @click="openActionBuilder"
            >
              Открыть конструктор действий
            </button>

            <!-- Actions Preview -->
            <div v-if="actions.length > 0" class="actions-preview">
              <strong>Действия:</strong>
              <div style="font-size: 12px; margin-top: 5px;">
                <div v-for="(action, index) in actions" :key="index">
                  {{ index + 1 }}. {{ getActionDescription(action) }}
                </div>
              </div>
            </div>

            <div class="info-box">
              <strong>Обработка данных (опционально)</strong>
              <p style="font-size: 13px; margin-top: 5px;">
                Используйте регулярные выражения для извлечения и форматирования данных
              </p>
            </div>

            <div class="form-group">
              <label for="regexPattern">Regex шаблон (для извлечения)</label>
              <input
                id="regexPattern"
                v-model="ruleEditor.regexPattern"
                type="text"
                class="form-control"
                placeholder="Например: (\d+) или ([A-F0-9:]+)"
              />
            </div>

            <div class="form-group">
              <label for="regexReplacement">Regex замена (опционально)</label>
              <input
                id="regexReplacement"
                v-model="ruleEditor.regexReplacement"
                type="text"
                class="form-control"
                placeholder="Например: \1 или $1"
              />
            </div>
          </div>
        </div>

        <!-- Calculated Rule Block -->
        <div v-else id="calculatedRuleBlock">
          <div class="info-box warning">
            <strong>Вычисляемое поле</strong>
            <p style="font-size: 13px; margin-top: 5px;">
              Выберите сохраненные правила для использования в вычислениях.
            </p>
          </div>

          <div class="form-group">
            <label>Использовать данные из сохраненных правил:</label>
            <div class="rules-selector">
              <div
                v-for="rule in existingRules.filter(r => !r.is_calculated)"
                :key="rule.id"
                class="checkbox-group"
              >
                <input
                  :id="'use_rule_' + rule.id"
                  v-model="selectedRulesForCalc"
                  type="checkbox"
                  :value="rule.id"
                  @change="updateCalculationFormula"
                />
                <label :for="'use_rule_' + rule.id">
                  <strong>{{ rule.field_name }}</strong>
                  <span style="color: #6c757d;">({{ rule.protocol }}://{{ printerIp }}{{ rule.url_path }})</span>
                </label>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label for="calculationFormula">Формула вычисления</label>
            <input
              id="calculationFormula"
              v-model="ruleEditor.calculationFormula"
              type="text"
              class="form-control"
              placeholder="Например: rule_1 + rule_2 - rule_3"
            />
            <small style="color: #6c757d;">Используйте rule_ID для ссылки на правила</small>
          </div>
        </div>

        <!-- Save Rule Button -->
        <div class="button-group mt-3">
          <button
            class="btn btn-success"
            :disabled="!canSaveRule"
            @click="saveRule"
          >
            <i class="bi bi-save me-1"></i>
            Сохранить правило
          </button>
        </div>

        <!-- Rules List -->
        <div class="rules-list mt-4">
          <h3>Сохранённые правила</h3>

          <div v-if="!existingRules.length" class="empty-rules">
            Нет сохраненных правил парсинга
          </div>

          <div
            v-for="rule in existingRules"
            :key="rule.id"
            class="rule-item"
            :class="{ calculated: rule.is_calculated }"
          >
            <div class="rule-info">
              <strong>
                {{ rule.field_name }}
                <span v-if="rule.is_calculated" class="rule-badge">ВЫЧИСЛЯЕМОЕ</span>
              </strong>
              <div v-if="rule.is_calculated">
                Формула: {{ rule.calculation_formula }}
              </div>
              <div v-else>
                {{ rule.protocol }}://{{ printerIp }}{{ rule.url_path }}<br>
                <small v-if="rule.actions_chain">Действий: {{ JSON.parse(rule.actions_chain || '[]').length }}</small>
              </div>
            </div>
            <div class="button-group">
              <button
                v-if="!rule.is_calculated"
                class="btn btn-sm btn-secondary"
                @click="viewActions(rule)"
              >
                Просмотреть
              </button>
              <button
                class="btn btn-sm btn-warning"
                @click="editRule(rule)"
              >
                Редактировать
              </button>
              <button
                class="btn btn-sm btn-danger"
                @click="deleteRule(rule.id)"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>

        <!-- Templates -->
        <div class="mt-4">
          <h3>Шаблоны</h3>

          <div class="form-group">
            <label>Шаблон</label>
            <select v-model="selectedTemplate" class="form-select">
              <option value="">— выберите шаблон —</option>
              <option
                v-for="template in templates"
                :key="template.id"
                :value="template.id"
              >
                {{ template.name }}
              </option>
            </select>
          </div>

          <div v-if="selectedTemplateDescription" class="alert alert-info mt-2">
            {{ selectedTemplateDescription }}
          </div>

          <div class="button-group mt-2">
            <button
              class="btn btn-outline-primary"
              :disabled="!selectedTemplate"
              @click="applyTemplate"
            >
              <i class="bi bi-download me-1"></i>
              Применить шаблон
            </button>
            <button
              class="btn btn-outline-success"
              :disabled="!existingRules.length"
              @click="openTemplateModal"
            >
              <i class="bi bi-save me-1"></i>
              Сохранить как шаблон
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Action Builder Modal -->
    <div
      v-if="showActionBuilder"
      class="modal fade show"
      style="display: block"
      tabindex="-1"
    >
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Конструктор действий</h5>
            <button
              type="button"
              class="btn-close"
              @click="closeActionBuilder"
            ></button>
          </div>
          <div class="modal-body">
            <div class="action-builder-grid">
              <!-- Left: Actions -->
              <div>
                <h6>Действия</h6>

                <div class="button-group mb-3">
                  <button class="btn btn-sm btn-primary" @click="addBuilderAction('click')">
                    <i class="bi bi-cursor"></i> Клик
                  </button>
                  <button class="btn btn-sm btn-secondary" @click="addBuilderAction('send_keys')">
                    <i class="bi bi-pencil"></i> Ввод
                  </button>
                  <button class="btn btn-sm btn-secondary" @click="addBuilderAction('wait')">
                    <i class="bi bi-clock"></i> Ожидание
                  </button>
                  <button class="btn btn-sm btn-success" @click="addBuilderAction('parse')">
                    <i class="bi bi-code"></i> Парсинг XPath
                  </button>
                </div>

                <!-- Actions List -->
                <div class="actions-builder-list">
                  <div
                    v-for="(action, index) in builderActions"
                    :key="index"
                    class="action-builder-item"
                  >
                    <div class="action-item-header">
                      <strong>{{ getActionTypeLabel(action.type) }} #{{ index + 1 }}</strong>
                      <button class="btn btn-sm btn-danger" @click="removeBuilderAction(index)">
                        <i class="bi bi-trash"></i>
                      </button>
                    </div>

                    <!-- Click Action -->
                    <div v-if="action.type === 'click'">
                      <input
                        v-model="action.selector"
                        type="text"
                        class="form-control mb-2"
                        placeholder="CSS селектор (например: #tab2)"
                      />
                      <input
                        v-model.number="action.wait"
                        type="number"
                        class="form-control"
                        placeholder="Ожидание после (сек)"
                        min="0"
                        max="10"
                      />
                    </div>

                    <!-- Send Keys Action -->
                    <div v-else-if="action.type === 'send_keys'">
                      <input
                        v-model="action.selector"
                        type="text"
                        class="form-control mb-2"
                        placeholder="CSS селектор"
                      />
                      <input
                        v-model="action.value"
                        type="text"
                        class="form-control mb-2"
                        placeholder="Текст для ввода"
                      />
                      <input
                        v-model.number="action.wait"
                        type="number"
                        class="form-control"
                        placeholder="Ожидание после (сек)"
                        min="0"
                        max="10"
                      />
                    </div>

                    <!-- Wait Action -->
                    <div v-else-if="action.type === 'wait'">
                      <input
                        v-model.number="action.wait"
                        type="number"
                        class="form-control"
                        placeholder="Секунд"
                        min="1"
                        max="10"
                      />
                    </div>

                    <!-- Parse Action -->
                    <div v-else-if="action.type === 'parse'">
                      <input
                        v-model="action.xpath"
                        type="text"
                        class="form-control mb-2"
                        placeholder="XPath выражение"
                      />
                      <input
                        v-model="action.regex"
                        type="text"
                        class="form-control mb-2"
                        placeholder="Regex (опционально)"
                      />
                      <input
                        v-model="action.var_name"
                        type="text"
                        class="form-control"
                        placeholder="Имя переменной"
                      />
                    </div>
                  </div>
                </div>

                <div class="button-group mt-3">
                  <button class="btn btn-success" @click="executeActions">
                    <i class="bi bi-play"></i> Выполнить
                  </button>
                  <button class="btn btn-danger" @click="clearBuilderActions">
                    <i class="bi bi-x"></i> Очистить
                  </button>
                </div>
              </div>

              <!-- Right: Result -->
              <div>
                <h6>Результат</h6>

                <div class="action-log">
                  <div v-if="actionLog.length === 0" class="text-muted">
                    Выполните действия чтобы увидеть результат
                  </div>
                  <div v-else>
                    <div v-for="(log, index) in actionLog" :key="index" v-html="log"></div>
                  </div>
                </div>

                <button class="btn btn-secondary w-100 mb-2" @click="viewHtmlSource">
                  Посмотреть HTML
                </button>

                <button class="btn btn-success w-100" @click="saveActionsAndClose">
                  Сохранить действия
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showActionBuilder" class="modal-backdrop fade show"></div>

    <!-- HTML View Modal -->
    <div
      v-if="showHtmlView"
      class="modal fade show"
      style="display: block"
      tabindex="-1"
    >
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">HTML источник</h5>
            <button
              type="button"
              class="btn-close"
              @click="closeHtmlView"
            ></button>
          </div>
          <div class="modal-body">
            <textarea
              v-model="lastExecutedHtml"
              class="form-control"
              rows="20"
              style="font-family: monospace; font-size: 11px;"
              readonly
            ></textarea>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showHtmlView" class="modal-backdrop fade show"></div>

    <!-- View Actions Modal -->
    <div
      v-if="showViewActions"
      class="modal fade show"
      style="display: block"
      tabindex="-1"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Порядок действий</h5>
            <button
              type="button"
              class="btn-close"
              @click="closeViewActions"
            ></button>
          </div>
          <div class="modal-body">
            <div style="font-size: 14px; line-height: 1.6;">
              <div v-for="(action, index) in viewActionsData" :key="index">
                {{ index + 1 }}. {{ getActionDescription(action) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showViewActions" class="modal-backdrop fade show"></div>

    <!-- Template Save Modal -->
    <div
      v-if="showTemplateModal"
      class="modal fade show"
      style="display: block"
      tabindex="-1"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Сохранить как шаблон</h5>
            <button
              type="button"
              class="btn-close"
              @click="closeTemplateModal"
            ></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label for="templateName" class="form-label">Название шаблона *</label>
              <input
                id="templateName"
                v-model="templateForm.name"
                type="text"
                class="form-control"
                placeholder="Например: HP LaserJet M404"
                required
              />
            </div>
            <div class="mb-3">
              <label for="templateDescription" class="form-label">Описание</label>
              <textarea
                id="templateDescription"
                v-model="templateForm.description"
                class="form-control"
                rows="3"
                placeholder="Краткое описание шаблона (необязательно)"
              ></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              @click="closeTemplateModal"
            >
              Отмена
            </button>
            <button
              type="button"
              class="btn btn-success"
              :disabled="!templateForm.name.trim()"
              @click="saveAsTemplate"
            >
              <i class="bi bi-save me-1"></i>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showTemplateModal" class="modal-backdrop fade show"></div>

    <!-- Toast уведомления -->
    <ToastContainer />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useToast } from '../../composables/useToast'
import ToastContainer from '../common/ToastContainer.vue'

const props = defineProps({
  printerId: {
    type: [Number, String],
    required: true
  },
  printerIp: {
    type: String,
    required: true
  },
  deviceModelId: {
    type: [Number, String],
    default: null
  }
})

const appConfig = inject('appConfig', {})

// Toast notifications
const { showToast } = useToast()

// State
const config = reactive({
  protocol: 'http',
  urlPath: '/',
  username: '',
  password: ''
})

const ruleEditor = reactive({
  fieldName: '',
  isCalculated: false,
  regexPattern: '',
  regexReplacement: '',
  calculationFormula: '',
  editId: null
})

const currentHtml = ref('')
const currentUrl = ref('')
const finalUrl = ref('')
const proxyUrl = ref('')
const isLoadingPage = ref(false)
const isLoadingIframe = ref(false)
const iframeRef = ref(null)
const testResult = ref('')
const fieldDescription = ref('')
const testXpathValue = ref('')
const testRegexValue = ref('')

const actions = ref([])
const existingRules = ref([])
const selectedRulesForCalc = ref([])
const templates = ref([])
const selectedTemplate = ref('')
const showTemplateModal = ref(false)
const templateForm = reactive({
  name: '',
  description: ''
})

// Action Builder
const showActionBuilder = ref(false)
const builderActions = ref([])
const actionLog = ref([])
const lastExecutedHtml = ref('')
const showHtmlView = ref(false)
const showViewActions = ref(false)
const viewActionsData = ref([])

let iframeLoadTimeout = null

const returnQueryString = ref('')

const returnUrl = computed(() => {
  const baseUrl = '/inventory/'
  return returnQueryString.value ? `${baseUrl}?${returnQueryString.value}` : baseUrl
})

const canSaveRule = computed(() => {
  if (!ruleEditor.fieldName) return false
  if (ruleEditor.isCalculated) {
    return !!ruleEditor.calculationFormula
  }
  return actions.value.length > 0 && actions.value.some(a => a.type === 'parse')
})

const selectedTemplateDescription = computed(() => {
  if (!selectedTemplate.value) return ''
  const template = templates.value.find(t => t.id === selectedTemplate.value)
  return template?.description || ''
})

// Utility functions
function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

function showMessage(text, type = 'info') {
  const titles = {
    success: 'Успех',
    error: 'Ошибка',
    warning: 'Предупреждение',
    info: 'Информация'
  }
  showToast(titles[type] || titles.info, text, type)
}

function updateFieldDescription() {
  const descriptions = {
    'counter': 'Общий счётчик отпечатанных страниц',
    'counter_a4_bw': 'Счётчик чёрно-белых страниц формата A4',
    'counter_a3_bw': 'Счётчик чёрно-белых страниц формата A3',
    'counter_a4_color': 'Счётчик цветных страниц формата A4',
    'counter_a3_color': 'Счётчик цветных страниц формата A3',
    'serial_number': 'Серийный номер устройства',
    'mac_address': 'MAC-адрес устройства',
    'toner_black': 'Уровень чёрного тонера (%)',
    'toner_cyan': 'Уровень голубого тонера (%)',
    'toner_magenta': 'Уровень пурпурного тонера (%)',
    'toner_yellow': 'Уровень жёлтого тонера (%)',
    'drum_black': 'Уровень ресурса чёрного барабана (%)',
    'drum_cyan': 'Уровень ресурса голубого барабана (%)',
    'drum_magenta': 'Уровень ресурса пурпурного барабана (%)',
    'drum_yellow': 'Уровень ресурса жёлтого барабана (%)'
  }
  fieldDescription.value = descriptions[ruleEditor.fieldName] || ''
}

function toggleCalculatedMode() {
  if (ruleEditor.isCalculated) {
    actions.value = []
  } else {
    ruleEditor.calculationFormula = ''
    selectedRulesForCalc.value = []
  }
}

function updateCalculationFormula() {
  const selectedIds = selectedRulesForCalc.value
  if (selectedIds.length > 0) {
    const formula = selectedIds.map(id => `rule_${id}`).join(' + ')
    ruleEditor.calculationFormula = formula
  }
}

// Load printer page
async function loadPrinterPage() {
  isLoadingPage.value = true

  try {
    if (!props.printerIp) {
      showMessage('Ошибка: IP адрес принтера не указан', 'error')
      isLoadingPage.value = false
      return
    }

    const url = `${config.protocol}://${props.printerIp}${config.urlPath}`

    const response = await fetch('/inventory/api/web-parser/fetch-page/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        url,
        username: config.username,
        password: config.password
      })
    })

    const result = await response.json()

    if (result.success) {
      currentHtml.value = result.content
      currentUrl.value = result.url
      finalUrl.value = result.url

      isLoadingIframe.value = true

      let proxy = `/inventory/api/web-parser/proxy-page/?url=${encodeURIComponent(result.url)}`
      if (config.username) {
        proxy += `&username=${encodeURIComponent(config.username)}&password=${encodeURIComponent(config.password)}`
      }
      proxyUrl.value = proxy

      if (iframeLoadTimeout) clearTimeout(iframeLoadTimeout)
      iframeLoadTimeout = setTimeout(() => {
        isLoadingIframe.value = false
        showMessage('Страница загружена (timeout)', 'warning')
      }, 30000)

      showMessage('Страница загружена успешно', 'success')
    } else {
      showMessage(`Ошибка: ${result.error || 'Неизвестная ошибка'}`, 'error')
    }
  } catch (error) {
    console.error('Error loading page:', error)
    showMessage('Ошибка при загрузке страницы', 'error')
  } finally {
    isLoadingPage.value = false
  }
}

function openInNewTab() {
  if (currentUrl.value) {
    window.open(currentUrl.value, '_blank')
  }
}

function copyFinalUrl() {
  if (finalUrl.value) {
    navigator.clipboard.writeText(finalUrl.value)
    showMessage('URL скопирован в буфер обмена', 'success')
  }
}

function onIframeLoad() {
  setTimeout(() => {
    isLoadingIframe.value = false
    if (iframeLoadTimeout) {
      clearTimeout(iframeLoadTimeout)
      iframeLoadTimeout = null
    }
  }, 1000)
}

// Test XPath
async function testXpath() {
  if (!currentHtml.value || !testXpathValue.value) {
    showMessage('Сначала загрузите страницу и введите XPath', 'error')
    return
  }

  try {
    const response = await fetch('/inventory/api/web-parser/test-xpath/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        html: currentHtml.value,
        xpath: testXpathValue.value,
        regex_pattern: testRegexValue.value
      })
    })

    const result = await response.json()

    if (result.success) {
      testResult.value = result.processed_result || result.raw_result || ''
      showMessage('XPath протестирован успешно', 'success')
    } else {
      testResult.value = `Ошибка: ${result.error || 'Неизвестная ошибка'}`
      showMessage('Ошибка при тестировании XPath', 'error')
    }
  } catch (error) {
    console.error('Error testing XPath:', error)
    showMessage('Ошибка при тестировании', 'error')
  }
}

// Action Builder Functions
function openActionBuilder() {
  if (!currentHtml.value) {
    showMessage('Сначала загрузите страницу принтера', 'error')
    return
  }
  // Load existing actions if editing
  builderActions.value = JSON.parse(JSON.stringify(actions.value))
  showActionBuilder.value = true
}

function closeActionBuilder() {
  showActionBuilder.value = false
}

function addBuilderAction(type) {
  const action = { type }

  if (type === 'click' || type === 'send_keys') {
    action.selector = ''
    action.wait = 1
  }

  if (type === 'send_keys') {
    action.value = ''
  }

  if (type === 'wait') {
    action.wait = 2
  }

  if (type === 'parse') {
    action.xpath = ''
    action.regex = ''
    action.var_name = 'parsed_value'
  }

  builderActions.value.push(action)
}

function removeBuilderAction(index) {
  builderActions.value.splice(index, 1)
}

function clearBuilderActions() {
  if (confirm('Очистить все действия?')) {
    builderActions.value = []
    actionLog.value = []
  }
}

async function executeActions() {
  const url = `${config.protocol}://${props.printerIp}${config.urlPath}`

  // Validation
  for (const action of builderActions.value) {
    if ((action.type === 'click' || action.type === 'send_keys') && !action.selector) {
      showMessage('Заполните CSS селектор', 'error')
      return
    }
    if (action.type === 'parse' && !action.xpath) {
      showMessage('Заполните XPath выражение', 'error')
      return
    }
  }

  actionLog.value = ['Выполнение...']

  try {
    const response = await fetch('/inventory/api/web-parser/execute-action/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        url,
        actions: builderActions.value,
        username: config.username,
        password: config.password
      })
    })

    const result = await response.json()

    if (result.success) {
      lastExecutedHtml.value = result.html || ''
      currentHtml.value = result.html || ''
      actionLog.value = result.action_log || []
      actionLog.value.push('<strong style="color: green;">✓ Успешно!</strong>')
      showMessage('Действия выполнены успешно!', 'success')
    } else {
      actionLog.value = result.action_log || []
      actionLog.value.push(`<strong style="color: red;">✗ Ошибка: ${result.error}</strong>`)
      showMessage('Ошибка выполнения действий', 'error')
    }
  } catch (error) {
    console.error('Error executing actions:', error)
    actionLog.value = [`✗ Ошибка: ${error.message}`]
    showMessage('Ошибка: ' + error.message, 'error')
  }
}

function viewHtmlSource() {
  if (!lastExecutedHtml.value) {
    showMessage('Сначала выполните действия', 'error')
    return
  }
  showHtmlView.value = true
}

function closeHtmlView() {
  showHtmlView.value = false
}

function saveActionsAndClose() {
  actions.value = JSON.parse(JSON.stringify(builderActions.value))
  closeActionBuilder()
  showMessage('Действия сохранены!', 'success')
}

function getActionTypeLabel(type) {
  const labels = {
    click: 'Клик',
    send_keys: 'Ввод',
    wait: 'Ожидание',
    parse: 'Парсинг'
  }
  return labels[type] || type
}

function getActionDescription(action) {
  if (action.type === 'click') {
    return `Клик: ${action.selector} (ожидание ${action.wait}с)`
  }
  if (action.type === 'send_keys') {
    return `Ввод: ${action.selector} = "${action.value}" (ожидание ${action.wait}с)`
  }
  if (action.type === 'wait') {
    return `Ожидание: ${action.wait}с`
  }
  if (action.type === 'parse') {
    return `Парсинг: ${action.xpath}${action.regex ? ' (regex: ' + action.regex + ')' : ''}${action.var_name ? ' -> ' + action.var_name : ''}`
  }
  return ''
}

// View actions modal
function viewActions(rule) {
  if (!rule.actions_chain) return

  try {
    viewActionsData.value = JSON.parse(rule.actions_chain)
    showViewActions.value = true
  } catch (e) {
    showMessage('Ошибка при чтении действий', 'error')
  }
}

function closeViewActions() {
  showViewActions.value = false
  viewActionsData.value = []
}

// Save rule
async function saveRule() {
  if (!canSaveRule.value) return

  try {
    const parseActions = actions.value.filter(a => a.type === 'parse')
    if (!ruleEditor.isCalculated && parseActions.length !== 1) {
      showMessage('Должно быть ровно одно действие парсинга в конце цепочки', 'error')
      return
    }

    const data = {
      printer_id: props.printerId,
      protocol: config.protocol,
      url_path: config.urlPath,
      field_name: ruleEditor.fieldName,
      is_calculated: ruleEditor.isCalculated
    }

    if (ruleEditor.isCalculated) {
      data.source_rules = JSON.stringify(selectedRulesForCalc.value)
      data.calculation_formula = ruleEditor.calculationFormula
      data.xpath = ''
      data.actions_chain = ''
      data.regex_pattern = ''
      data.regex_replacement = ''
    } else {
      const parseAction = parseActions[0]
      data.xpath = parseAction.xpath
      data.actions_chain = JSON.stringify(actions.value)
      data.regex_pattern = ruleEditor.regexPattern || parseAction.regex || ''
      data.regex_replacement = ruleEditor.regexReplacement || ''
    }

    const response = await fetch('/inventory/api/web-parser/save-rule/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(data)
    })

    const result = await response.json()

    if (result.success) {
      showMessage('Правило сохранено успешно!', 'success')
      await loadRules()
      cancelEdit()
    } else {
      showMessage(`Ошибка: ${result.error || 'Неизвестная ошибка'}`, 'error')
    }
  } catch (error) {
    console.error('Error saving rule:', error)
    showMessage('Ошибка при сохранении правила', 'error')
  }
}

function editRule(rule) {
  ruleEditor.editId = rule.id
  ruleEditor.fieldName = rule.field_name
  ruleEditor.isCalculated = rule.is_calculated

  config.protocol = rule.protocol
  config.urlPath = rule.url_path

  if (rule.is_calculated) {
    try {
      selectedRulesForCalc.value = JSON.parse(rule.source_rules || '[]')
    } catch {
      selectedRulesForCalc.value = []
    }
    ruleEditor.calculationFormula = rule.calculation_formula || ''
  } else {
    ruleEditor.regexPattern = rule.regex_pattern || ''
    ruleEditor.regexReplacement = rule.regex_replacement || ''

    try {
      actions.value = JSON.parse(rule.actions_chain || '[]')
    } catch {
      actions.value = []
    }
  }

  updateFieldDescription()
  showMessage('Правило загружено для редактирования', 'success')
}

function cancelEdit() {
  ruleEditor.editId = null
  ruleEditor.fieldName = ''
  ruleEditor.isCalculated = false
  ruleEditor.regexPattern = ''
  ruleEditor.regexReplacement = ''
  ruleEditor.calculationFormula = ''
  selectedRulesForCalc.value = []
  actions.value = []
  testResult.value = ''
  fieldDescription.value = ''
}

async function deleteRule(ruleId) {
  if (!confirm('Удалить это правило парсинга?')) return

  try {
    const response = await fetch(`/inventory/api/web-parser/delete-rule/${ruleId}/`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    })

    if (response.ok) {
      showMessage('Правило удалено', 'success')
      await loadRules()
    } else {
      showMessage('Ошибка удаления', 'error')
    }
  } catch (error) {
    console.error('Error deleting rule:', error)
    showMessage('Ошибка: ' + error.message, 'error')
  }
}

// Load rules
async function loadRules() {
  try {
    const response = await fetch(`/inventory/api/web-parser/rules/${props.printerId}/`)
    if (response.ok) {
      const data = await response.json()
      existingRules.value = data.rules || []
    }
  } catch (error) {
    console.error('Error loading rules:', error)
  }
}

// Templates
async function loadTemplates() {
  try {
    if (!props.deviceModelId) {
      templates.value = []
      return
    }

    const response = await fetch(`/inventory/api/web-parser/templates/?device_model_id=${props.deviceModelId}`)
    const data = await response.json()
    templates.value = data.templates || []

    if (templates.value.length > 0) {
      showMessage(`Найдено ${templates.value.length} шаблон(ов)`, 'info')
    }
  } catch (error) {
    console.error('Error loading templates:', error)
  }
}

async function applyTemplate() {
  if (!selectedTemplate.value) return

  try {
    const response = await fetch('/inventory/api/web-parser/apply-template/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        printer_id: props.printerId,
        template_id: selectedTemplate.value
      })
    })

    const result = await response.json()

    if (result.success) {
      showMessage(result.message || 'Шаблон применён', 'success')
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } else {
      showMessage(`Ошибка: ${result.error || 'Неизвестная ошибка'}`, 'error')
    }
  } catch (error) {
    console.error('Error applying template:', error)
    showMessage('Ошибка при применении шаблона', 'error')
  }
}

function openTemplateModal() {
  templateForm.name = ''
  templateForm.description = ''
  showTemplateModal.value = true
}

function closeTemplateModal() {
  showTemplateModal.value = false
  templateForm.name = ''
  templateForm.description = ''
}

async function saveAsTemplate() {
  if (!templateForm.name.trim()) return

  try {
    const response = await fetch('/inventory/api/web-parser/save-template/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        printer_id: props.printerId,
        template_name: templateForm.name.trim(),
        description: templateForm.description.trim(),
        is_public: false
      })
    })

    const result = await response.json()

    if (result.success) {
      showMessage('Шаблон сохранён', 'success')
      closeTemplateModal()
      await loadTemplates()
    } else {
      showMessage(`Ошибка: ${result.error || 'Неизвестная ошибка'}`, 'error')
    }
  } catch (error) {
    console.error('Error saving template:', error)
    showMessage('Ошибка при сохранении шаблона', 'error')
  }
}

// Lifecycle
onMounted(async () => {
  if (document.referrer) {
    try {
      const referrerUrl = new URL(document.referrer)
      if (referrerUrl.pathname.includes('/inventory/')) {
        returnQueryString.value = referrerUrl.search.substring(1)
      }
    } catch (e) {
      // Ignore
    }
  }

  if (appConfig.initialData?.rules) {
    existingRules.value = appConfig.initialData.rules
  }
  if (appConfig.initialData?.templates) {
    templates.value = appConfig.initialData.templates
  }

  await loadRules()
  await loadTemplates()
})
</script>

<style scoped>
.web-parser-container {
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px;
}

.parser-header {
  background: white;
  padding: 20px 30px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.parser-header h1 {
  color: #333;
  font-size: 24px;
  margin: 0;
}

.printer-info {
  color: #6c757d;
  font-size: 14px;
  margin-top: 5px;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.panel {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.panel h2 {
  color: #333;
  font-size: 20px;
  margin: 0 0 20px 0;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
}

.panel h3 {
  color: #333;
  font-size: 16px;
  margin: 20px 0 10px 0;
}

.form-row {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 10px;
  margin-bottom: 15px;
  align-items: start;
}

.form-row label {
  font-weight: 500;
  color: #495057;
  padding-top: 8px;
}

.form-row-auth {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 15px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  color: #495057;
  font-weight: 500;
}

.button-group {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.checkbox-group {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.checkbox-group input[type="checkbox"] {
  width: auto;
  margin-right: 10px;
}

.checkbox-group label {
  margin: 0;
  cursor: pointer;
}

.preview-container {
  width: 100%;
  height: 600px;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  margin-bottom: 15px;
  overflow: hidden;
}

.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6c757d;
  font-size: 14px;
}

#webFrame {
  width: 100%;
  height: 100%;
}

.info-box {
  background: #e7f3ff;
  border-left: 4px solid #007bff;
  padding: 12px;
  margin-bottom: 15px;
  border-radius: 4px;
  font-size: 14px;
}

.info-box.warning {
  background: #fff3cd;
  border-color: #ffc107;
}

.test-result {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  border-left: 3px solid #28a745;
  margin-top: 10px;
}

.advanced-options {
  border-top: 1px solid #dee2e6;
  padding-top: 15px;
  margin-top: 15px;
}

.actions-preview {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 15px;
}

.rules-list {
  margin-top: 20px;
}

.rule-item {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rule-item.calculated {
  border-left: 4px solid #ffc107;
}

.rule-info {
  flex: 1;
}

.rule-info strong {
  color: #007bff;
  display: block;
  margin-bottom: 5px;
}

.rule-badge {
  background: #ffc107;
  color: #000;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: bold;
  margin-left: 8px;
}

.empty-rules {
  text-align: center;
  padding: 40px 20px;
  color: #6c757d;
}

.rules-selector {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 10px;
  background: #f8f9fa;
}

/* Action Builder Styles */
.action-builder-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.actions-builder-list {
  max-height: 400px;
  overflow-y: auto;
}

.action-builder-item {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 10px;
  border-left: 3px solid #007bff;
}

.action-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.action-log {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 15px;
  min-height: 100px;
  max-height: 200px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 12px;
}

/* Modal Styles */
.modal {
  z-index: 1050;
}

.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1040;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.5);
}

.modal-dialog {
  position: relative;
  width: auto;
  margin: 1.75rem auto;
  max-width: 500px;
}

.modal-dialog.modal-xl {
  max-width: 1200px;
}

.modal-content {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  pointer-events: auto;
  background-color: #fff;
  background-clip: padding-box;
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-radius: 0.3rem;
  outline: 0;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid #dee2e6;
}

.modal-title {
  margin: 0;
  line-height: 1.5;
  font-size: 1.25rem;
}

.modal-body {
  position: relative;
  flex: 1 1 auto;
  padding: 1rem;
}

.modal-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  padding: 0.75rem;
  border-top: 1px solid #dee2e6;
  gap: 0.5rem;
}

@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .action-builder-grid {
    grid-template-columns: 1fr;
  }
}
</style>
