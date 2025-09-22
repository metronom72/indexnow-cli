#!/bin/bash

# SEO Sitemap CLI Tool - Скрипт установки и настройки

set -e  # Остановка при ошибке

echo "🚀 Настройка SEO Sitemap CLI Tool"
echo "================================="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+ и повторите попытку."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Найден Python $PYTHON_VERSION"

# Создание виртуального окружения
echo "📦 Создание виртуального окружения..."
python3 -m venv venv

# Активация виртуального окружения
echo "🔄 Активация виртуального окружения..."
source venv/bin/activate

# Обновление pip
echo "⬆️ Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
echo "📚 Установка зависимостей..."
pip install -r requirements.txt

# Делаем скрипт исполняемым
echo "🔧 Настройка прав доступа..."
chmod +x seo_sitemap_cli.py

# Создание символической ссылки (опционально)
if [[ "$1" == "--global" ]]; then
    echo "🌐 Создание глобальной команды..."
    sudo ln -sf "$(pwd)/seo_sitemap_cli.py" /usr/local/bin/seo-sitemap
    echo "✅ Команда 'seo-sitemap' доступна глобально"
fi

echo ""
echo "✅ Установка завершена!"
echo ""
echo "🎯 Быстрый старт:"
echo "  source venv/bin/activate"
echo "  python seo_sitemap_cli.py --help"
echo ""
echo "📖 Примеры использования:"
echo "  python seo_sitemap_cli.py check-availability https://example.com/sitemap.xml"
echo "  python seo_sitemap_cli.py analyze https://example.com/sitemap.xml"
echo ""
echo "🔗 Для работы с IndexNow подготовьте API ключ согласно README.md"