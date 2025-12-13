#!/bin/bash

# Скрипт для удобного запуска Locust тестов
# Использование: ./run_locust.sh [режим] [дополнительные параметры]

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка установки Locust
check_locust() {
    if ! command -v locust &> /dev/null; then
        log_error "Locust не установлен!"
        echo "Установите: pip install locust"
        exit 1
    fi
    log_success "Locust установлен: $(locust --version)"
}

# Проверка запущенного сервера
check_server() {
    local host="${1:-http://localhost:8000}"
    log_info "Проверка доступности сервера: $host"

    if curl -s -o /dev/null -w "%{http_code}" "$host/accounts/login/" | grep -q "200\|302"; then
        log_success "Сервер доступен"
    else
        log_warning "Сервер недоступен по адресу $host"
        log_warning "Убедитесь, что приложение запущено:"
        echo "  python manage.py runserver 0.0.0.0:8000"
    fi
}

# Функция помощи
show_help() {
    cat << EOF
${GREEN}Скрипт запуска Locust тестов для Printer Inventory Django${NC}

${YELLOW}Использование:${NC}
    ./run_locust.sh [режим] [параметры]

${YELLOW}Режимы:${NC}
    web          - Запуск с веб-интерфейсом (по умолчанию)
    quick        - Быстрый тест (10 пользователей, 1 минута)
    medium       - Средний тест (50 пользователей, 5 минут)
    stress       - Стресс-тест (200 пользователей, 10 минут)
    django       - Тест только Django авторизации
    keycloak     - Тест только Keycloak авторизации
    anonymous    - Тест анонимных пользователей
    mixed        - Смешанный тест (все типы пользователей)

${YELLOW}Примеры:${NC}
    ./run_locust.sh web
    ./run_locust.sh quick
    ./run_locust.sh stress --host=http://192.168.1.100:8000
    ./run_locust.sh django --users=20 --run-time=2m

${YELLOW}Переменные окружения:${NC}
    LOCUST_HOST              - URL приложения (по умолчанию: http://localhost:8000)
    LOCUST_DJANGO_USER       - Django username (по умолчанию: locust_test)
    LOCUST_DJANGO_PASSWORD   - Django password (по умолчанию: locust_password_123)
    LOCUST_KEYCLOAK_USER     - Keycloak username (по умолчанию: user)
    LOCUST_KEYCLOAK_PASSWORD - Keycloak password (по умолчанию: 12345678)

EOF
}

# Создание директории для результатов
mkdir -p tests/locust/results
mkdir -p tests/locust/logs

# Базовые параметры
HOST="${LOCUST_HOST:-http://localhost:8000}"
LOCUSTFILE="locustfile.py"
RESULTS_DIR="tests/locust/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Проверка установки Locust
check_locust

# Обработка режимов
MODE="${1:-web}"
shift || true  # Удаляем первый аргумент, остальные передаем в locust

case "$MODE" in
    help|--help|-h)
        show_help
        exit 0
        ;;

    web)
        log_info "Запуск Locust с веб-интерфейсом"
        check_server "$HOST"
        echo ""
        log_success "Откройте http://localhost:8089 в браузере"
        echo ""
        locust -f "$LOCUSTFILE" --host="$HOST" "$@"
        ;;

    quick)
        log_info "Быстрый тест: 10 пользователей, 1 минута"
        check_server "$HOST"
        locust -f "$LOCUSTFILE" \
            --host="$HOST" \
            --users=10 \
            --spawn-rate=2 \
            --run-time=1m \
            --headless \
            --csv="$RESULTS_DIR/quick_$TIMESTAMP" \
            --html="$RESULTS_DIR/quick_$TIMESTAMP.html" \
            "$@"
        log_success "Результаты сохранены в $RESULTS_DIR/quick_$TIMESTAMP.*"
        ;;

    medium)
        log_info "Средний тест: 50 пользователей, 5 минут"
        check_server "$HOST"
        locust -f "$LOCUSTFILE" \
            --host="$HOST" \
            --users=50 \
            --spawn-rate=5 \
            --run-time=5m \
            --headless \
            --csv="$RESULTS_DIR/medium_$TIMESTAMP" \
            --html="$RESULTS_DIR/medium_$TIMESTAMP.html" \
            "$@"
        log_success "Результаты сохранены в $RESULTS_DIR/medium_$TIMESTAMP.*"
        ;;

    stress)
        log_warning "СТРЕСС-ТЕСТ: 200 пользователей, 10 минут"
        log_warning "Убедитесь, что сервер готов к высокой нагрузке!"
        sleep 2
        check_server "$HOST"
        locust -f "$LOCUSTFILE" \
            --host="$HOST" \
            --users=200 \
            --spawn-rate=10 \
            --run-time=10m \
            --headless \
            --csv="$RESULTS_DIR/stress_$TIMESTAMP" \
            --html="$RESULTS_DIR/stress_$TIMESTAMP.html" \
            "$@"
        log_success "Результаты сохранены в $RESULTS_DIR/stress_$TIMESTAMP.*"
        ;;

    django)
        log_info "Тест Django авторизации"
        check_server "$HOST"
        locust -f "$LOCUSTFILE" DjangoAuthUser \
            --host="$HOST" \
            --headless \
            --users=10 \
            --spawn-rate=2 \
            --run-time=2m \
            --csv="$RESULTS_DIR/django_$TIMESTAMP" \
            "$@"
        ;;

    keycloak)
        log_info "Тест Keycloak авторизации"
        log_warning "Убедитесь, что Keycloak запущен: docker-compose up keycloak"
        sleep 1
        check_server "$HOST"
        locust -f "$LOCUSTFILE" KeycloakAuthUser \
            --host="$HOST" \
            --headless \
            --users=10 \
            --spawn-rate=2 \
            --run-time=2m \
            --csv="$RESULTS_DIR/keycloak_$TIMESTAMP" \
            "$@"
        ;;

    anonymous)
        log_info "Тест анонимных пользователей"
        check_server "$HOST"
        locust -f "$LOCUSTFILE" AnonymousUser \
            --host="$HOST" \
            --headless \
            --users=20 \
            --spawn-rate=5 \
            --run-time=2m \
            --csv="$RESULTS_DIR/anonymous_$TIMESTAMP" \
            "$@"
        ;;

    mixed)
        log_info "Смешанный тест (все типы пользователей)"
        check_server "$HOST"
        locust -f "$LOCUSTFILE" MixedUser \
            --host="$HOST" \
            --headless \
            --users=30 \
            --spawn-rate=3 \
            --run-time=3m \
            --csv="$RESULTS_DIR/mixed_$TIMESTAMP" \
            --html="$RESULTS_DIR/mixed_$TIMESTAMP.html" \
            "$@"
        ;;

    *)
        log_error "Неизвестный режим: $MODE"
        echo ""
        show_help
        exit 1
        ;;
esac
