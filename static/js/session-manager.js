/**
 * Session Manager
 * Автоматическое продление сессии и обработка истечения токенов
 */

class SessionManager {
  constructor(options = {}) {
    this.heartbeatInterval = options.heartbeatInterval || 5 * 60 * 1000; // 5 минут по умолчанию
    this.heartbeatUrl = options.heartbeatUrl || '/api/heartbeat/';
    this.loginUrl = options.loginUrl || '/accounts/login/';
    this.enabled = options.enabled !== false;
    this.debug = options.debug || false;

    this.heartbeatTimer = null;
    this.lastActivity = Date.now();
    this.isRefreshing = false;

    if (this.enabled) {
      this.init();
    }
  }

  log(...args) {
    if (this.debug) {
      console.log('[SessionManager]', ...args);
    }
  }

  init() {
    this.log('Initializing...');

    // Отслеживаем активность пользователя
    this.trackUserActivity();

    // Запускаем heartbeat
    this.startHeartbeat();

    // Перехватываем fetch запросы для обработки 401/403
    this.interceptFetch();

    this.log('Initialized');
  }

  trackUserActivity() {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

    events.forEach(event => {
      document.addEventListener(event, () => {
        this.lastActivity = Date.now();
      }, { passive: true });
    });
  }

  startHeartbeat() {
    this.log('Starting heartbeat with interval:', this.heartbeatInterval);

    // Первый heartbeat через минуту
    setTimeout(() => this.sendHeartbeat(), 60 * 1000);

    // Затем регулярные heartbeats
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
  }

  async sendHeartbeat() {
    // Не отправляем heartbeat если пользователь неактивен больше 30 минут
    const inactiveTime = Date.now() - this.lastActivity;
    if (inactiveTime > 30 * 60 * 1000) {
      this.log('User inactive for', Math.floor(inactiveTime / 1000 / 60), 'minutes, skipping heartbeat');
      return;
    }

    try {
      this.log('Sending heartbeat...');
      const response = await fetch(this.heartbeatUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': this.getCSRFToken(),
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
      });

      if (response.ok) {
        this.log('Heartbeat OK');
      } else if (response.status === 401 || response.status === 403) {
        this.log('Heartbeat failed: unauthorized');
        this.handleSessionExpired();
      } else {
        this.log('Heartbeat failed:', response.status);
      }
    } catch (error) {
      this.log('Heartbeat error:', error);
    }
  }

  interceptFetch() {
    const originalFetch = window.fetch;
    const self = this;

    window.fetch = async function(...args) {
      const response = await originalFetch.apply(this, args);

      // Если получили 401 или 403 на API запросе
      if ((response.status === 401 || response.status === 403) && !self.isRefreshing) {
        const url = args[0];

        // Игнорируем heartbeat и auth endpoints
        if (typeof url === 'string' &&
            !url.includes('/api/heartbeat/') &&
            !url.includes('/accounts/') &&
            !url.includes('/oidc/')) {

          self.log('Received', response.status, 'for', url);

          // Пробуем обновить сессию
          const refreshed = await self.tryRefreshSession();

          if (refreshed) {
            self.log('Session refreshed, retrying request');
            // Повторяем запрос
            return originalFetch.apply(this, args);
          } else {
            self.log('Session refresh failed');
            self.handleSessionExpired();
          }
        }
      }

      return response;
    };
  }

  async tryRefreshSession() {
    if (this.isRefreshing) {
      this.log('Already refreshing, waiting...');
      return false;
    }

    this.isRefreshing = true;

    try {
      this.log('Trying to refresh session...');

      // Делаем простой GET запрос на текущую страницу
      // Это заставит SessionRefresh middleware обновить токены
      const response = await fetch(window.location.href, {
        method: 'HEAD',
        credentials: 'same-origin'
      });

      this.isRefreshing = false;

      if (response.ok) {
        this.log('Session refreshed successfully');
        return true;
      } else {
        this.log('Session refresh failed:', response.status);
        return false;
      }
    } catch (error) {
      this.isRefreshing = false;
      this.log('Session refresh error:', error);
      return false;
    }
  }

  handleSessionExpired() {
    this.log('Session expired, redirecting to login...');

    // Показываем уведомление
    this.showSessionExpiredNotification();

    // Через 3 секунды редиректим на логин
    setTimeout(() => {
      const currentUrl = window.location.pathname + window.location.search;
      window.location.href = `${this.loginUrl}?next=${encodeURIComponent(currentUrl)}`;
    }, 3000);
  }

  showSessionExpiredNotification() {
    // Используем toast если доступен
    if (typeof showToast === 'function') {
      showToast(
        'Сессия истекла',
        'Вы долго не проявляли активность. Через 3 секунды вы будете перенаправлены на страницу входа. После повторного входа вы вернетесь на эту страницу.',
        'warning'
      );
      return;
    }

    // Иначе показываем alert
    alert('Ваша сессия истекла из-за длительного бездействия.\n\nВы будете перенаправлены на страницу входа.\nПосле повторного входа вы вернетесь на эту страницу.');
  }

  getCSRFToken() {
    // Пробуем получить из meta тега
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) {
      return meta.getAttribute('content');
    }

    // Пробуем получить из cookie
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  destroy() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.log('Destroyed');
  }
}

// Автоматически инициализируем если пользователь авторизован
if (document.body.classList.contains('auth')) {
  // Инициализируем после загрузки DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.sessionManager = new SessionManager({
        heartbeatInterval: 5 * 60 * 1000, // 5 минут
        debug: false // Включите true для отладки
      });
    });
  } else {
    window.sessionManager = new SessionManager({
      heartbeatInterval: 5 * 60 * 1000,
      debug: false
    });
  }
}
