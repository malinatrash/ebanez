# 🤖 Ebanez - AI-Powered Telegram Chat Bot

Ebanez - это умный Telegram бот, который становится частью вашего чата, обучаясь на сообщениях участников и генерируя контент в стиле вашего сообщества. Использует продвинутые алгоритмы машинного обучения на основе цепей Маркова для создания уникального и контекстно-релевантного контента.

## ✨ Особенности

### 🧠 Умное Обучение
- Анализирует сообщения в чате и учится воспроизводить уникальный стиль общения
- Адаптируется к сленгу, мемам и особенностям речи вашего сообщества
- Сохраняет отдельную модель для каждого чата

### 🎯 Контекстная Генерация
- Создает сообщения, которые звучат естественно и соответствуют стилю чата
- Поддерживает эмодзи и форматирование текста
- Генерирует случайные, но осмысленные ответы

### 🎨 Работа со Стикерами
- Запоминает и использует стикеры, популярные в чате
- Реагирует на сообщения подходящими стикерами
- Учится правильно использовать стикеры в контексте разговора

### 📊 Аналитика
- Отслеживает статистику активности чата
- Показывает информацию о количестве обработанных сообщений
- Предоставляет инсайты о паттернах общения

### 🛠 Управление
- `/gen` - генерирует сообщение в стиле чата
- `/stats` - показывает статистику обучения
- `/clear` - позволяет начать обучение заново
- `/rebuild` - обновляет модель с текущими данными

## 🔧 Технологии

- Python 3.11
- python-telegram-bot
- SQLite для хранения данных
- Цепи Маркова для генерации текста
- Docker для развертывания
- GitHub Actions для CI/CD

## 🚀 Производительность

- Мгновенная обработка сообщений
- Эффективное использование памяти благодаря SQLite
- Автоматическое сохранение и восстановление моделей
- Контейнеризация для простого масштабирования

## 📈 Постоянное Развитие

Бот постоянно совершенствуется, изучая новые паттерны общения и адаптируясь к изменениям в чате. Чем больше сообщений обрабатывается, тем более естественным становится генерируемый контент.
