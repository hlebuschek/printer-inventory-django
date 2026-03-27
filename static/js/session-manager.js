/**
 * Session Manager
 * Автоматическое продление сессии и прозрачная реавторизация через Keycloak.
 *
 * При истечении OIDC-токена (после бездействия) выполняет silent re-auth
 * через скрытый iframe: Keycloak с prompt=none прозрачно обновляет сессию,
 * после чего оригинальный запрос повторяется. Пользователь ничего не замечает.
 */

class SessionManager {
  constructor(options = {}) {
    this.heartbeatInterval = options.heartbeatInterval || 5 * 60 * 1000;
    this.heartbeatUrl = options.heartbeatUrl || '/api/heartbeat/';
    this.loginUrl = options.loginUrl || '/accounts/login/';
    this.reauthUrl = options.reauthUrl || '/oidc/authenticate/';
    this.reauthCompleteUrl = options.reauthCompleteUrl || '/api/reauth-complete/';
    this.enabled = options.enabled !== false;
    this.debug = options.debug || false;

    this.heartbeatTimer = null;
    this.lastActivity = Date.now();
    this.reauthInProgress = null; // Promise, если реавторизация идёт
    this.reauthFailed = false;

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
    this.trackUserActivity();
    this.startHeartbeat();
    this.interceptFetch();
    this.log('Initialized');
  }

  trackUserActivity() {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

    events.forEach(event => {
      document.addEventListener(event, () => {
        const wasInactive = (Date.now() - this.lastActivity) > 30 * 60 * 1000;
        this.lastActivity = Date.now();

        if (wasInactive) {
          this.log('User returned after inactivity, checking session...');
          this.sendHeartbeat();
        }
      }, { passive: true });
    });
  }

  startHeartbeat() {
    this.log('Starting heartbeat with interval:', this.heartbeatInterval);
    setTimeout(() => this.sendHeartbeat(), 60 * 1000);
    this.heartbeatTimer = setInterval(() => this.sendHeartbeat(), this.heartbeatInterval);
  }

  async sendHeartbeat() {
    const inactiveTime = Date.now() - this.lastActivity;
    if (inactiveTime > 30 * 60 * 1000) {
      this.log('User inactive, skipping heartbeat');
      return;
    }

    try {
      this.log('Sending heartbeat...');
      const originalFetch = window._originalFetch || window.fetch;
      const response = await originalFetch.call(window, this.heartbeatUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': this.getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
      });

      if (response.ok) {
        this.log('Heartbeat OK');
      } else if (response.status === 401 || response.status === 403) {
        this.log('Heartbeat: session expired, attempting silent reauth...');
        const success = await this.silentReauth();
        if (!success) {
          this.redirectToLogin();
        }
      }
    } catch (error) {
      this.log('Heartbeat error:', error);
    }
  }

  interceptFetch() {
    const originalFetch = window.fetch;
    window._originalFetch = originalFetch;
    const self = this;

    window.fetch = async function(...args) {
      let response;
      try {
        response = await originalFetch.apply(this, args);
      } catch (error) {
        // CSP блокировка или сеть недоступна
        const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
        if (self._isAppUrl(url)) {
          self.log('Fetch error for', url, '- attempting silent reauth');
          const success = await self.silentReauth();
          if (success) {
            return originalFetch.apply(this, args);
          }
          self.redirectToLogin();
        }
        throw error;
      }

      // 401 — сессия истекла
      if (response.status === 401) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
        if (self._isAppUrl(url)) {
          self.log('Got 401 for', url, '- attempting silent reauth');
          const success = await self.silentReauth();
          if (success) {
            self.log('Silent reauth succeeded, retrying request');
            return originalFetch.apply(this, args);
          }
          self.log('Silent reauth failed, redirecting to login');
          self.redirectToLogin();
        }
      }

      return response;
    };
  }

  /**
   * Прозрачная реавторизация через скрытый iframe.
   * Keycloak сессия обычно ещё жива — prompt=none авторизует без UI.
   * После успешной реавторизации Django session cookie обновляется.
   * @returns {Promise<boolean>} true если реавторизация успешна
   */
  async silentReauth() {
    // Если реавторизация уже была неудачной в этой сессии — не повторяем
    if (this.reauthFailed) {
      return false;
    }

    // Если реавторизация уже идёт — ждём её результат
    if (this.reauthInProgress) {
      this.log('Reauth already in progress, waiting...');
      return this.reauthInProgress;
    }

    this.log('Starting silent reauth via iframe...');

    this.reauthInProgress = new Promise((resolve) => {
      const iframe = document.createElement('iframe');
      iframe.style.display = 'none';
      iframe.setAttribute('aria-hidden', 'true');

      let resolved = false;
      const cleanup = (success) => {
        if (resolved) return;
        resolved = true;
        window.removeEventListener('message', onMessage);
        if (iframe.parentNode) {
          iframe.parentNode.removeChild(iframe);
        }
        this.reauthInProgress = null;
        if (!success) {
          this.reauthFailed = true;
        }
        this.log('Silent reauth', success ? 'succeeded' : 'failed');
        resolve(success);
      };

      // Слушаем postMessage от iframe (reauth-complete page)
      const onMessage = (event) => {
        if (event.origin !== window.location.origin) return;
        if (event.data && event.data.type === 'reauth-ok') {
          cleanup(true);
        }
      };
      window.addEventListener('message', onMessage);

      // Таймаут 15 секунд
      setTimeout(() => cleanup(false), 15000);

      // iframe ошибка
      iframe.onerror = () => cleanup(false);

      // Запускаем OIDC flow в iframe
      const reauthUrl = `${this.reauthUrl}?next=${encodeURIComponent(this.reauthCompleteUrl)}`;
      iframe.src = reauthUrl;
      document.body.appendChild(iframe);
    });

    return this.reauthInProgress;
  }

  redirectToLogin() {
    if (this._redirecting) return;
    this._redirecting = true;

    this.log('Redirecting to login...');
    const currentUrl = window.location.pathname + window.location.search;
    window.location.href = `${this.loginUrl}?next=${encodeURIComponent(currentUrl)}`;
  }

  _isAppUrl(url) {
    return url &&
      !url.includes('/api/heartbeat/') &&
      !url.includes('/accounts/') &&
      !url.includes('/oidc/') &&
      !url.includes('/api/reauth-complete/');
  }

  getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');

    const name = 'csrftoken';
    if (document.cookie) {
      const cookies = document.cookie.split(';');
      for (const cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name + '=')) {
          return decodeURIComponent(trimmed.substring(name.length + 1));
        }
      }
    }
    return null;
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
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.sessionManager = new SessionManager({
        heartbeatInterval: 5 * 60 * 1000,
        debug: false
      });
    });
  } else {
    window.sessionManager = new SessionManager({
      heartbeatInterval: 5 * 60 * 1000,
      debug: false
    });
  }
}
