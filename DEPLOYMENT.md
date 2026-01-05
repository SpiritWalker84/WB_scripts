# Инструкция по развертыванию

## Быстрый старт

### 1. Подготовка окружения

```bash
# Перейдите в директорию проекта
cd /home/rinat/wildberries/wb_full

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка конфигурации

```bash
# Скопируйте пример конфигурации
cp .env.example .env

# Отредактируйте .env файл
nano .env
```

Заполните все необходимые переменные (см. `.env.example`)

### 3. Проверка готовности

```bash
python3 check_setup_price.py
```

Убедитесь, что все проверки пройдены успешно.

### 4. Первый запуск

```bash
python3 run_full_update.py
```

## Настройка автоматического запуска

### Вариант 1: Systemd (рекомендуется)

Создайте файл `/etc/systemd/system/wb-update.service`:

```ini
[Unit]
Description=Wildberries Full Update Service
After=network.target

[Service]
Type=oneshot
User=rinat
WorkingDirectory=/home/rinat/wildberries/wb_full
Environment="PATH=/home/rinat/wildberries/wb_full/venv/bin:/usr/bin"
ExecStart=/home/rinat/wildberries/wb_full/venv/bin/python /home/rinat/wildberries/wb_full/run_full_update.py
StandardOutput=journal
StandardError=journal
```

Создайте таймер `/etc/systemd/system/wb-update.timer`:

```ini
[Unit]
Description=Wildberries Update Timer

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wb-update.timer
sudo systemctl start wb-update.timer
sudo systemctl status wb-update.timer
```

### Вариант 2: Cron

Добавьте в crontab:

```bash
crontab -e
```

Добавьте строку (запуск каждый день в 2:00):

```cron
0 2 * * * cd /home/rinat/wildberries/wb_full && /home/rinat/wildberries/wb_full/venv/bin/python run_full_update.py >> /var/log/wb_update.log 2>&1
```

## Структура директорий

```
/home/rinat/wildberries/
├── wb_full/              # Скрипты проекта
│   ├── venv/            # Виртуальное окружение
│   ├── .env             # Конфигурация (не в git)
│   └── *.py             # Скрипты
├── tmp/                 # Временные файлы (архивы)
└── price/               # Прайс-файлы по брендам
    ├── brand_BOSCH.csv
    ├── brand_TRIALLI.csv
    └── brand_MANN.csv
```

## Проверка работы

### Логи systemd

```bash
sudo journalctl -u wb-update.service -f
```

### Ручной запуск

```bash
cd /home/rinat/wildberries/wb_full
source venv/bin/activate
python3 run_full_update.py
```

## Обновление

```bash
cd /home/rinat/wildberries/wb_full
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

## Откат изменений

```bash
cd /home/rinat/wildberries/wb_full
git log                    # Просмотр истории
git checkout <commit-hash> # Откат к конкретному коммиту
```

