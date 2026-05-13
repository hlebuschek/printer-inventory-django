// Запуск фонового Excel-экспорта Okdesk:
// 1) GET на endpoint экспорта → backend ставит Celery-таск, возвращает task_id;
// 2) поллим /integrations/okdesk/sync-status/?ids=<task_id>;
// 3) когда ready — кликаем по download_url, который стримит готовый файл.
//
// Раньше экспорт был синхронный (`<a href>` → backend генерирует xlsx
// в потоке запроса). При большом количестве заявок это блокировало
// ASGI-worker и мешало всем пользователям. Теперь — фоновая задача.

import { ref } from 'vue'
import { useToast } from './useToast'

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 10 * 60 * 1000

export function useOkdeskExport() {
  const exporting = ref(false)
  const { showToast } = useToast()

  async function startExport(url, { successText = 'Файл готов, скачивание начнётся автоматически' } = {}) {
    if (exporting.value) return
    exporting.value = true
    try {
      const resp = await fetch(url, { method: 'GET' })
      if (!resp.ok && resp.status !== 202) {
        const text = await resp.text()
        throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`)
      }
      const data = await resp.json()
      if (!data.task_id || !data.download_url) {
        throw new Error('Сервер не вернул task_id/download_url')
      }

      showToast('Формируется файл', 'Подождите несколько секунд...', 'info')

      const started = Date.now()
      while (Date.now() - started < POLL_TIMEOUT_MS) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
        const sresp = await fetch(data.status_url)
        if (!sresp.ok) continue
        const sdata = await sresp.json()
        if (!sdata.all_done) continue
        const taskInfo = sdata.tasks[data.task_id]
        if (taskInfo?.error) throw new Error(taskInfo.error)

        // Целевой бинарь готов — кликаем по download_url. Используем
        // временный <a download>, чтобы не было навигации страницы.
        const link = document.createElement('a')
        link.href = data.download_url
        document.body.appendChild(link)
        link.click()
        link.remove()
        showToast('Готово', successText, 'success')
        return
      }
      throw new Error('Таймаут формирования файла')
    } catch (e) {
      showToast('Ошибка экспорта', e.message, 'error')
    } finally {
      exporting.value = false
    }
  }

  return { startExport, exporting }
}
