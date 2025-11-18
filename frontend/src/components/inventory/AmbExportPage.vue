<template>
  <div class="row justify-content-center">
    <div class="col-12 col-sm-10 col-md-8 col-lg-6">
      <h2 class="mb-4">Отчет для АМБ</h2>

      <div class="alert alert-info mb-4">
        <i class="bi bi-info-circle me-2"></i>
        Загрузите шаблон Excel для генерации отчета АМБ
      </div>

      <form @submit.prevent="handleSubmit">
        <div class="mb-3">
          <label for="template" class="form-label">Шаблон Excel</label>
          <input
            id="template"
            ref="fileInput"
            type="file"
            class="form-control"
            accept=".xlsx,.xls"
            required
            @change="onFileChange"
          />
          <div class="form-text">
            Выберите файл Excel шаблона для заполнения данными из инвентаря
          </div>
        </div>

        <div v-if="selectedFile" class="mb-3">
          <div class="alert alert-secondary">
            <i class="bi bi-file-earmark-excel me-2"></i>
            {{ selectedFile.name }} ({{ formatFileSize(selectedFile.size) }})
          </div>
        </div>

        <div class="d-flex gap-2">
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="!selectedFile || isSubmitting"
          >
            <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2"></span>
            <i v-else class="bi bi-download me-1"></i>
            {{ isSubmitting ? 'Генерация...' : 'Сгенерировать отчет' }}
          </button>
          <a href="/inventory/" class="btn btn-secondary">
            <i class="bi bi-x-lg"></i> Отмена
          </a>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const fileInput = ref(null)
const selectedFile = ref(null)
const isSubmitting = ref(false)

function onFileChange(event) {
  const files = event.target.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? match.pop() : ''
}

async function handleSubmit() {
  if (!selectedFile.value) return

  isSubmitting.value = true

  try {
    const formData = new FormData()
    formData.append('template', selectedFile.value)

    const response = await fetch('/inventory/export-amb/', {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    })

    if (response.ok) {
      // Download the file
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'amb_report.xlsx'
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      // Reset form
      selectedFile.value = null
      if (fileInput.value) {
        fileInput.value.value = ''
      }

      // Show success message
      alert('Отчет успешно сгенерирован!')
    } else {
      const text = await response.text()
      alert('Ошибка: ' + text)
    }
  } catch (error) {
    console.error('Error generating report:', error)
    alert('Ошибка при генерации отчета')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.form-text {
  font-size: 0.875rem;
  color: #6c757d;
}
</style>
