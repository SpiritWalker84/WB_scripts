#!/bin/bash
# Скрипт для запуска очистки остатков с автоматическим использованием venv

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "Виртуальное окружение не найдено. Создаю..."
    python3 -m venv venv
    
    if [ $? -ne 0 ]; then
        echo "Ошибка: Не удалось создать виртуальное окружение"
        echo "Убедитесь, что установлен python3-venv: sudo apt install python3-venv"
        exit 1
    fi
    
    echo "Виртуальное окружение создано"
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем установлены ли зависимости
if ! python3 -c "import dotenv" 2>/dev/null; then
    echo "Устанавливаю зависимости..."
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "Ошибка: Не удалось установить зависимости"
        exit 1
    fi
fi

# Запускаем скрипт
python3 clear_wb_stocks.py

# Сохраняем код выхода
EXIT_CODE=$?

# Деактивируем виртуальное окружение
deactivate

exit $EXIT_CODE

