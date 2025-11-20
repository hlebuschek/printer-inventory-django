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
        <a href="/inventory/" class="btn btn-secondary">
          <i class="bi bi-arrow-left"></i> Назад к списку
        </a>
      </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
      <!-- Left Panel: Configuration & Preview -->
      <div class="panel">
        <h2>Конфигурация и предпросмотр</h2>

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
        <div class="checkbox-group">
          <input
            id="requiresAuth"
            v-model="config.requiresAuth"
            type="checkbox"
          />
          <label for="requiresAuth">Требуется авторизация</label>
        </div>

        <div v-if="config.requiresAuth" class="form-row-auth">
          <input
            v-model="config.username"
            type="text"
            class="form-control"
            placeholder="Логин"
          />
          <input
            v-model="config.password"
            type="password"
            class="form-control"
            placeholder="Пароль"
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

        <!-- Actions Section -->
        <div v-if="currentHtml" class="mt-3">
          <h3>Действия</h3>
          <div class="button-group">
            <button class="btn btn-sm btn-outline-primary" @click="addAction('click')">
              <i class="bi bi-cursor me-1"></i> Click
            </button>
            <button class="btn btn-sm btn-outline-primary" @click="addAction('fill')">
              <i class="bi bi-pencil me-1"></i> Fill
            </button>
            <button class="btn btn-sm btn-outline-success" @click="addAction('parse')">
              <i class="bi bi-code me-1"></i> Parse
            </button>
          </div>

          <!-- Actions List -->
          <div v-if="actions.length" class="actions-list mt-2">
            <div
              v-for="(action, index) in actions"
              :key="index"
              class="action-item"
            >
              <span class="action-badge" :class="'badge-' + action.type">
                {{ index + 1 }}. {{ action.type.toUpperCase() }}
              </span>
              <span class="action-details">{{ action.details || 'Не настроено' }}</span>
              <button
                class="btn btn-sm btn-danger"
                @click="removeAction(index)"
              >
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Rule Editor & List -->
      <div class="panel">
        <h2>Правила парсинга</h2>

        <!-- Field Selector -->
        <div class="form-row">
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

        <div v-if="fieldDescription" class="info-box">
          <code>{{ fieldDescription }}</code>
        </div>

        <!-- Calculated Mode Toggle -->
        <div class="checkbox-group">
          <input
            id="isCalculated"
            v-model="ruleEditor.isCalculated"
            type="checkbox"
            @change="toggleCalculatedMode"
          />
          <label for="isCalculated">Расчётное поле (формула)</label>
        </div>

        <!-- Normal Rule Block -->
        <div v-if="!ruleEditor.isCalculated" id="normalRuleBlock">
          <div class="form-row">
            <label>XPath</label>
            <textarea
              v-model="ruleEditor.xpath"
              class="form-control"
              rows="2"
              placeholder="//div[@id='counter']/text()"
            ></textarea>
          </div>

          <div class="form-row">
            <label>Regex</label>
            <input
              v-model="ruleEditor.regex"
              type="text"
              class="form-control"
              placeholder="\d+"
            />
          </div>

          <!-- Test XPath -->
          <div class="button-group">
            <button
              class="btn btn-outline-primary"
              :disabled="!currentHtml || !ruleEditor.xpath"
              @click="testXpath"
            >
              <i class="bi bi-play me-1"></i>
              Тестировать XPath
            </button>
          </div>

          <div v-if="testResult" class="test-result mt-2">
            <strong>Результат:</strong> {{ testResult }}
          </div>
        </div>

        <!-- Calculated Rule Block -->
        <div v-else id="calculatedRuleBlock">
          <div class="info-box mb-3">
            Выберите поля для расчёта (например: total_pages = bw_a4 + color_a4)
          </div>

          <!-- Rule Selector for Calculation -->
          <div id="rulesSelector" class="rules-selector mb-3">
            <div
              v-for="rule in existingRules"
              :key="rule.id"
              class="form-check"
            >
              <input
                :id="'rule-' + rule.id"
                v-model="selectedRulesForCalc"
                type="checkbox"
                :value="rule.id"
                class="form-check-input"
              />
              <label :for="'rule-' + rule.id" class="form-check-label">
                {{ rule.field_name }}
              </label>
            </div>
          </div>

          <div class="form-row">
            <label>Формула</label>
            <input
              v-model="ruleEditor.formula"
              type="text"
              class="form-control"
              placeholder="bw_a4 + color_a4"
            />
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
            {{ ruleEditor.editId ? 'Обновить правило' : 'Сохранить правило' }}
          </button>
          <button
            v-if="ruleEditor.editId"
            class="btn btn-secondary"
            @click="cancelEdit"
          >
            Отмена
          </button>
        </div>

        <!-- Rules List -->
        <div class="rules-list mt-4">
          <h3>Сохранённые правила</h3>

          <div v-if="!existingRules.length" class="empty-rules">
            Правила ещё не созданы
          </div>

          <div
            v-for="rule in existingRules"
            :key="rule.id"
            class="rule-item"
            :class="{ calculated: rule.is_calculated }"
          >
            <div class="rule-info">
              <strong>{{ rule.field_name }}</strong>
              <span v-if="rule.is_calculated" class="rule-badge">CALC</span>
              <div v-if="rule.is_calculated">
                Формула: {{ rule.calculation_formula }}
              </div>
              <div v-else>
                XPath: {{ rule.xpath }}<br />
                <span v-if="rule.regex">Regex: {{ rule.regex }}</span>
              </div>
            </div>
            <div>
              <button
                class="btn btn-sm btn-primary me-1"
                @click="editRule(rule)"
              >
                <i class="bi bi-pencil"></i>
              </button>
              <button
                class="btn btn-sm btn-danger"
                @click="deleteRule(rule.id)"
              >
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- Templates -->
        <div class="mt-4">
          <h3>Шаблоны</h3>

          <div class="form-row">
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

          <!-- Template Description -->
          <div v-if="selectedTemplateDescription" class="alert alert-info mt-2">
            <strong>Описание:</strong> {{ selectedTemplateDescription }}
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
            <button
              v-if="selectedTemplate"
              class="btn btn-outline-danger"
              @click="deleteTemplate"
            >
              <i class="bi bi-trash me-1"></i>
              Удалить шаблон
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Template Save Modal -->
    <div
      v-if="showTemplateModal"
      class="modal fade show"
      style="display: block"
      tabindex="-1"
      @click.self="closeTemplateModal"
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
  requiresAuth: false,
  username: '',
  password: ''
})

const ruleEditor = reactive({
  fieldName: '',
  xpath: '',
  regex: '',
  isCalculated: false,
  formula: '',
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
let iframeLoadTimeout = null

const canSaveRule = computed(() => {
  if (!ruleEditor.fieldName) return false
  if (ruleEditor.isCalculated) {
    return !!ruleEditor.formula
  }
  return !!ruleEditor.xpath
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
    'serial_number': 'Серийный номер устройства. Пример XPath: //td[contains(text(),"Serial")]/following-sibling::td/text()',
    'mac_address': 'MAC-адрес устройства. Пример regex для извлечения: ([A-F0-9:]{17})',
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
    ruleEditor.xpath = ''
    ruleEditor.regex = ''
  } else {
    ruleEditor.formula = ''
    selectedRulesForCalc.value = []
  }
}

// Load printer page
async function loadPrinterPage() {
  isLoadingPage.value = true

  try {
    // Валидация IP адреса принтера
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

      // Показываем спиннер загрузки iframe
      isLoadingIframe.value = true

      // Формируем URL прокси с параметрами аутентификации (как в оригинале)
      let proxy = `/inventory/api/web-parser/proxy-page/?url=${encodeURIComponent(result.url)}`
      if (config.username) {
        proxy += `&username=${encodeURIComponent(config.username)}&password=${encodeURIComponent(config.password)}`
      }
      proxyUrl.value = proxy

      // Таймаут на случай если iframe не загрузится (30 сек)
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

// Iframe load handler
function onIframeLoad() {
  // Скрываем спиннер через 1 секунду после загрузки iframe (как в оригинале)
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
  if (!currentHtml.value || !ruleEditor.xpath) return

  try {
    const response = await fetch('/inventory/api/web-parser/test-xpath/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        html: currentHtml.value,
        xpath: ruleEditor.xpath,
        regex: ruleEditor.regex
      })
    })

    const result = await response.json()

    if (result.success) {
      testResult.value = result.raw_result || ''
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

// Save rule
async function saveRule() {
  if (!canSaveRule.value) return

  try {
    let parseAction = null
    const parseActions = actions.value.filter(a => a.type === 'parse')
    if (parseActions.length > 0) {
      parseAction = parseActions[0]
    }

    const data = {
      printer_id: props.printerId,
      protocol: config.protocol,
      url_path: config.urlPath,
      field_name: ruleEditor.fieldName,
      is_calculated: ruleEditor.isCalculated,
      edit_id: ruleEditor.editId || 0
    }

    if (ruleEditor.isCalculated) {
      data.calculation_formula = ruleEditor.formula
      data.selected_rules = selectedRulesForCalc.value
    } else {
      data.xpath = ruleEditor.xpath
      data.regex = ruleEditor.regex || ''

      if (parseAction) {
        data.actions = actions.value
        data.url = currentUrl.value
      }
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
      showMessage(ruleEditor.editId ? 'Правило обновлено' : 'Правило сохранено', 'success')
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

  if (rule.is_calculated) {
    ruleEditor.formula = rule.calculation_formula || ''
    selectedRulesForCalc.value = rule.selected_rules || []
  } else {
    ruleEditor.xpath = rule.xpath || ''
    ruleEditor.regex = rule.regex || ''
  }

  updateFieldDescription()
}

function cancelEdit() {
  ruleEditor.editId = null
  ruleEditor.fieldName = ''
  ruleEditor.xpath = ''
  ruleEditor.regex = ''
  ruleEditor.formula = ''
  ruleEditor.isCalculated = false
  selectedRulesForCalc.value = []
  testResult.value = ''
  fieldDescription.value = ''
}

async function deleteRule(ruleId) {
  if (!confirm('Удалить это правило?')) return

  try {
    const response = await fetch('/inventory/api/web-parser/save-rule/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        printer_id: props.printerId,
        edit_id: ruleId,
        delete: true
      })
    })

    const result = await response.json()

    if (result.success) {
      showMessage('Правило удалено', 'success')
      await loadRules()
    } else {
      showMessage(`Ошибка: ${result.error}`, 'error')
    }
  } catch (error) {
    console.error('Error deleting rule:', error)
    showMessage('Ошибка при удалении правила', 'error')
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

// Actions
function addAction(type) {
  actions.value.push({
    type,
    details: ''
  })
  showMessage(`Действие ${type} добавлено`, 'info')
}

function removeAction(index) {
  actions.value.splice(index, 1)
}

// Templates
async function loadTemplates() {
  try {
    // Загружаем шаблоны для модели принтера (как в оригинале)
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
      // Перезагружаем страницу через 1.5 секунды (как в оригинале)
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

async function deleteTemplate() {
  if (!selectedTemplate.value) return
  if (!confirm('Удалить этот шаблон?')) return

  try {
    const response = await fetch(`/inventory/api/web-parser/delete-template/${selectedTemplate.value}/`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    })

    const result = await response.json()

    if (result.success) {
      showMessage('Шаблон удалён', 'success')
      selectedTemplate.value = ''
      await loadTemplates()
    } else {
      showMessage(`Ошибка: ${result.error || 'Неизвестная ошибка'}`, 'error')
    }
  } catch (error) {
    console.error('Error deleting template:', error)
    showMessage('Ошибка при удалении шаблона', 'error')
  }
}

// Lifecycle
onMounted(async () => {
  // Load initial data from server if provided
  if (appConfig.initialData?.rules) {
    existingRules.value = appConfig.initialData.rules
  }
  if (appConfig.initialData?.templates) {
    templates.value = appConfig.initialData.templates
  }

  // Load fresh data from API
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
  height: 500px;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  margin-bottom: 15px;
  overflow: hidden;
}

.placeholder {
  display: flex;
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
  padding: 10px 15px;
  margin-bottom: 15px;
  border-radius: 4px;
  font-size: 14px;
}

.test-result {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  border-left: 3px solid #28a745;
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

.actions-list {
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 10px;
}

.action-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  margin-bottom: 5px;
}

.action-badge {
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: bold;
  color: white;
}

.action-badge.badge-click {
  background: #007bff;
}

.action-badge.badge-fill {
  background: #6c757d;
}

.action-badge.badge-parse {
  background: #28a745;
}

.action-details {
  flex: 1;
  margin: 0 10px;
  font-size: 14px;
  color: #495057;
}

.rules-selector {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 10px;
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
}
</style>
