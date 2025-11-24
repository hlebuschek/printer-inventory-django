/**
 * API client для работы с Django backend
 */

// Получение CSRF токена
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) return meta.content

  // Fallback: из cookie
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

// Базовая функция для fetch с обработкой ошибок
async function fetchApi(url, options = {}) {
  const defaultHeaders = {
    'X-CSRFToken': getCsrfToken(),
    'X-Requested-With': 'XMLHttpRequest',
  }

  // Если body - объект, конвертируем в JSON
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  }

  try {
    const response = await fetch(url, config)

    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}`)
      error.response = response
      error.status = response.status
      throw error
    }

    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return await response.json()
    }

    return await response.text()
  } catch (error) {
    console.error('API Error:', error)
    throw error
  }
}

// API методы для принтеров
export const printersApi = {
  // Получить список всех принтеров
  getAll: (params = {}) => {
    const queryString = new URLSearchParams(params).toString()
    return fetchApi(`/inventory/api/printers/${queryString ? '?' + queryString : ''}`)
  },

  // Получить один принтер
  getOne: (id) => fetchApi(`/inventory/api/printer/${id}/`),

  // Запустить опрос принтера
  runInventory: (id) => fetchApi(`/inventory/api/run-poll/${id}/`, { method: 'POST' }),

  // Запустить опрос всех принтеров
  runInventoryAll: () => fetchApi('/inventory/api/run-poll/', {
    method: 'POST',
    body: { all: true }
  }),

  // Обновить принтер
  update: (id, data) => fetchApi(`/inventory/edit/${id}/`, {
    method: 'POST',
    body: data
  }),

  // Удалить принтер
  delete: (id) => fetchApi(`/inventory/delete/${id}/`, { method: 'POST' }),

  // Получить историю принтера
  getHistory: (id) => fetchApi(`/inventory/history/${id}/`),

  // Получить все модели принтеров
  getAllModels: () => fetchApi('/inventory/api/all-printer-models/'),

  // Получить модели по производителю
  getModelsByManufacturer: (manufacturerId) =>
    fetchApi(`/inventory/api/models-by-manufacturer/?manufacturer_id=${manufacturerId}`)
}

// API методы для контрактов
export const contractsApi = {
  lookupBySerial: (serial) =>
    fetchApi(`/contracts/api/lookup-by-serial/?serial=${encodeURIComponent(serial)}`)
}

export default {
  printersApi,
  contractsApi,
  getCsrfToken
}
