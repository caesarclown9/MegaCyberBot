# MegaCyberBot 🤖

Telegram бот для автоматического парсинга и перевода новостей кибербезопасности с английского на русский язык.

## 🚀 Возможности

- **Автоматический парсинг** новостей из множества источников
- **Умный перевод** с английского на русский с помощью Google Translate
- **Множественные источники**: RSS ленты от ведущих изданий по кибербезопасности
- **Резервные источники**: если основной источник недоступен, бот переключается на альтернативные
- **Фильтрация дубликатов**: каждая новость публикуется только один раз
- **Настраиваемые интервалы**: гибкая настройка частоты проверки новостей

## 📰 Источники новостей

- 🇺🇸 The Hacker News (основной)
- 🔍 Krebs on Security
- 🌐 Dark Reading  
- ⚠️ Threatpost
- 👔 CSO Online
- 🛡️ Security Affairs
- 💻 BleepingComputer
- 🔒 SecurityWeek
- 📊 InfoSecurity Magazine

## 🛠️ Установка

### Требования
- Python 3.8+
- Telegram Bot Token
- ID Telegram группы/канала

### Быстрый старт

1. **Клонирование репозитория**
```bash
git clone https://github.com/caesarclown9/MegaCyberBot.git
cd MegaCyberBot
```

2. **Установка зависимостей**
```bash
pip install -r requirements.txt
```

3. **Настройка конфигурации**
```bash
cp .env.example .env
```

Отредактируйте `.env` файл:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_GROUP_ID=your_group_id_here
```

4. **Запуск бота**
```bash
python main.py
```

## ⚙️ Конфигурация

Все настройки находятся в файле `.env`:

```env
# Telegram настройки
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_GROUP_ID=your_group_id_here

# Настройки парсера
PARSE_INTERVAL_MINUTES=120        # Интервал проверки новостей (мин)
MAX_ARTICLES_PER_FETCH=5          # Максимум статей за раз
REQUEST_TIMEOUT_SECONDS=30        # Таймаут запросов
MIN_ARTICLE_DATE=2025-08-01       # Минимальная дата статей

# Перевод
TRANSLATION_TARGET_LANGUAGE=ru    # Целевой язык
TRANSLATION_SOURCE_LANGUAGE=auto  # Исходный язык

# Прокси (опционально)
# PROXY_URL=http://proxy:8080
# PROXY_USERNAME=username
# PROXY_PASSWORD=password

# Логирование
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## 🐳 Docker

```bash
# Сборка
docker build -t megacyberbot .

# Запуск
docker run -d --name megacyberbot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  megacyberbot
```

### Docker Compose
```bash
docker-compose up -d
```

## 📱 Как получить Telegram настройки

### Bot Token
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Получите токен вида: `123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`

### Group ID
1. Добавьте бота в группу как администратора
2. Отправьте любое сообщение в группу
3. Перейдите по ссылке: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Найдите `"chat":{"id":-1001234567890}` - это ваш Group ID

## 🔧 Архитектура

```
src/
├── bot/              # Telegram бот
│   ├── bot.py       # Основной класс бота
│   ├── handlers.py  # Обработчики команд
│   └── scheduler.py # Планировщик парсинга
├── parser/          # Парсеры новостей
│   ├── base.py      # Базовый класс
│   ├── hackernews.py    # The Hacker News
│   ├── cybersecurity.py # Альтернативные сайты
│   └── rss_feeds.py     # RSS ленты
├── database/        # База данных
│   ├── models.py    # SQLAlchemy модели
│   ├── connection.py # Подключение к БД
│   └── repositories.py # Репозитории
├── utils/          # Утилиты
│   ├── logger.py   # Логирование
│   ├── metrics.py  # Метрики
│   └── translator.py # Переводчик
└── config/         # Конфигурация
    └── settings.py # Настройки
```

## 📊 Мониторинг

Бот предоставляет метрики Prometheus на порту 8000:
- Количество обработанных статей
- Успешность переводов
- Время выполнения операций
- Активные пользователи

## 🔍 Логирование

Все логи в формате JSON с полной трассировкой:
- Парсинг статей  
- Переводы
- Отправка в Telegram
- Ошибки и предупреждения

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте ветку: `git checkout -b feature/amazing-feature`
3. Commit изменений: `git commit -m 'Add amazing feature'`
4. Push в ветку: `git push origin feature/amazing-feature`
5. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🐛 Сообщить об ошибке

Если вы нашли ошибку, пожалуйста, создайте [Issue](https://github.com/caesarclown9/MegaCyberBot/issues/new).

## ⭐ Поддержка

Если проект был полезен, поставьте звезду ⭐

---

**Создано с ❤️ для сообщества кибербезопасности**