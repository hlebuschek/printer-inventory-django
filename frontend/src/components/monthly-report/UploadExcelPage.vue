<template>
  <div class="container upload-form">
    <h1 class="h3 mb-4">
      <i class="bi bi-file-earmark-excel"></i>
      Загрузка отчета из Excel
    </h1>

    <div class="card shadow-sm">
      <div class="card-body">
        <form @submit.prevent="handleSubmit">
          <!-- File input -->
          <div class="mb-3">
            <label for="excelFile" class="form-label">Загрузить Excel-файл</label>
            <input
              id="excelFile"
              ref="fileInputRef"
              type="file"
              class="form-control"
              accept=".xlsx,.xls"
              @change="handleFileChange"
              :disabled="uploading"
              required
            >
          </div>

          <!-- Month input -->
          <div class="mb-3">
            <label for="month" class="form-label">Месяц (первый день)</label>
            <input
              id="month"
              v-model="formData.month"
              type="date"
              class="form-control"
              :disabled="uploading"
              required
            >
          </div>

          <!-- Replace month checkbox -->
          <div class="mb-3 form-check">
            <input
              id="replaceMonth"
              v-model="formData.replaceMonth"
              type="checkbox"
              class="form-check-input"
              :disabled="uploading"
            >
            <label for="replaceMonth" class="form-check-label">
              Очистить записи за месяц перед загрузкой
            </label>
          </div>

          <!-- Allow edit checkbox -->
          <div class="mb-3 form-check">
            <input
              id="allowEdit"
              v-model="formData.allowEdit"
              type="checkbox"
              class="form-check-input"
              :disabled="uploading"
            >
            <label for="allowEdit" class="form-check-label">
              Открыть отчёт для редактирования
            </label>
          </div>

          <!-- Edit until datetime -->
          <div v-if="formData.allowEdit" class="mb-3">
            <label for="editUntil" class="form-label">Запретить редактирование после</label>
            <input
              id="editUntil"
              v-model="formData.editUntil"
              type="datetime-local"
              class="form-control"
              :disabled="uploading"
            >
          </div>

          <!-- File info -->
          <div v-if="selectedFile" class="file-info">
            <i class="bi bi-file-earmark-check"></i>
            <strong>{{ selectedFile.name }}</strong> ({{ fileSizeFormatted }})
          </div>

          <!-- Progress bar -->
          <div v-if="uploading" class="progress-container active mt-3">
            <div class="progress">
              <div
                class="progress-bar progress-bar-striped progress-bar-animated"
                role="progressbar"
                style="width: 100%"
              >
                Обработка файла...
              </div>
            </div>
            <small class="text-muted d-block mt-2">
              Пожалуйста, не закрывайте страницу
            </small>
          </div>

          <!-- Error message -->
          <div v-if="error" class="alert alert-danger mt-3">
            {{ error }}
          </div>

          <!-- Success message -->
          <div v-if="success" class="alert alert-success mt-3">
            <i class="bi bi-check-circle"></i>
            {{ success }}
            <div v-if="uploadedMonthUrl" class="mt-2">
              <a :href="uploadedMonthUrl" class="btn btn-sm btn-success">
                <i class="bi bi-arrow-right"></i> Открыть отчет
              </a>
            </div>
          </div>

          <!-- Buttons -->
          <div class="mt-3">
            <button type="submit" class="btn btn-primary btn-upload" :disabled="uploading || !selectedFile">
              <span v-if="uploading" class="spinner"></span>
              <span v-if="!uploading">
                <i class="bi bi-upload"></i> Загрузить
              </span>
              <span v-else>
                <i class="bi bi-hourglass-split"></i> Загрузка...
              </span>
            </button>

            <a href="/monthly-report/" class="btn btn-outline-secondary ms-2" :class="{ 'disabled': uploading }">
              <i class="bi bi-arrow-left"></i> Отмена
            </a>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const fileInputRef = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const error = ref('')
const success = ref('')
const uploadedMonthUrl = ref('')

// Form data
const formData = ref({
  month: '',
  replaceMonth: false,
  allowEdit: false,
  editUntil: ''
})

// Formatted file size
const fileSizeFormatted = computed(() => {
  if (!selectedFile.value) return ''
  const sizeInMB = (selectedFile.value.size / (1024 * 1024)).toFixed(2)
  return `${sizeInMB} МБ`
})

// Handle file selection
function handleFileChange(event) {
  const file = event.target.files[0]
  selectedFile.value = file || null
  error.value = ''
  success.value = ''
}

// Get CSRF token
function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

// Handle form submission
async function handleSubmit() {
  if (!selectedFile.value) {
    error.value = 'Пожалуйста, выберите файл для загрузки'
    return
  }

  if (!formData.value.month) {
    error.value = 'Пожалуйста, выберите месяц'
    return
  }

  uploading.value = true
  error.value = ''
  success.value = ''

  try {
    const data = new FormData()
    data.append('excel_file', selectedFile.value)
    data.append('month', formData.value.month)
    data.append('replace_month', formData.value.replaceMonth ? 'on' : '')
    data.append('allow_edit', formData.value.allowEdit ? 'on' : '')
    if (formData.value.allowEdit && formData.value.editUntil) {
      data.append('edit_until', formData.value.editUntil)
    }

    const response = await fetch('/monthly-report/upload/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: data
    })

    const contentType = response.headers.get('content-type')

    if (contentType && contentType.includes('application/json')) {
      const responseData = await response.json()

      if (response.ok && responseData.success) {
        // Успешная загрузка
        success.value = responseData.message || 'Файл успешно загружен!'
        if (responseData.month_url) {
          uploadedMonthUrl.value = responseData.month_url
        }
        // Reset form
        selectedFile.value = null
        formData.value.month = ''
        formData.value.replaceMonth = false
        formData.value.allowEdit = false
        formData.value.editUntil = ''
        if (fileInputRef.value) {
          fileInputRef.value.value = ''
        }
      } else {
        // Ошибка из JSON ответа
        error.value = responseData.error || 'Произошла ошибка при загрузке файла'
      }
    } else {
      // Не JSON ответ
      const text = await response.text()
      if (response.ok) {
        // HTML успешный ответ - перенаправляем
        window.location.href = '/monthly-report/'
      } else {
        error.value = `Ошибка сервера: ${response.status} ${response.statusText}`
      }
    }
  } catch (err) {
    console.error('Upload error:', err)
    error.value = 'Не удалось загрузить файл. Проверьте подключение к интернету.'
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.upload-form {
  max-width: 600px;
  margin: 2rem auto;
}

.btn-upload {
  position: relative;
  min-width: 150px;
  transition: all 0.3s ease;
}

.btn-upload:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.btn-upload .spinner {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border: 2px solid #fff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 0.5rem;
  vertical-align: text-bottom;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.progress-container {
  display: none;
}

.progress-container.active {
  display: block;
}

.file-info {
  font-size: 0.875rem;
  color: #6c757d;
  margin-top: 0.5rem;
}

.file-info .bi {
  color: #0d6efd;
}
</style>
