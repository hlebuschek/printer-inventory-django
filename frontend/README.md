# Frontend - Vue.js приложение

> ⚠️ **ВАЖНО:** `index.html` в этой папке используется ТОЛЬКО для Vite dev server!
> Production использует Django шаблоны.

## Структура

```
frontend/
├── src/
│   ├── main.js           # Точка входа Vue.js  
│   ├── components/       # Vue компоненты
│   └── stores/           # Pinia stores
├── index.html           # Dev only (Vite dev server)
└── README.md
```

## Сборка

```bash
# Production build
npm run build

# Собрать Django статику
python manage.py collectstatic --noinput
```

Создаст файлы в `static/dist/`:
- `js/main.{hash}.js`
- `css/main.{hash}.css`  
- `.vite/manifest.json`

## Важно о vite.config.js

❌ **НЕ ДОБАВЛЯЙТЕ** `root: 'frontend'` в vite.config.js!

Это сломает ключи в manifest.json:
- ДО: `"frontend/src/main.js"` ✅
- ПОСЛЕ: `"src/main.js"` ❌

Django шаблоны ожидают `frontend/src/main.js` в manifest.
