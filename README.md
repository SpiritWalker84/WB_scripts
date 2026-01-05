# Wildberries: Полное обновление остатков и цен

Автоматизированная система для управления остатками и ценами товаров на Wildberries.

## Описание

Система состоит из трех основных скриптов, которые работают последовательно:

1. **clear_wb_stocks.py** - Удаление остатков товаров с Wildberries
2. **download_price.py** - Загрузка прайс-листов из почты и разбиение по брендам
3. **update_wb_stocks_prices.py** - Обновление цен и остатков на Wildberries

Также есть единый скрипт **run_full_update.py**, который выполняет все три операции последовательно.

## Возможности

- ✅ Автоматическая загрузка прайс-листов из почты Mail.ru
- ✅ Разбиение прайсов по брендам (BOSCH, TRIALLI, MANN)
- ✅ Обновление остатков на всех складах Wildberries
- ✅ Обновление цен с автоматическим повышением на 50%
- ✅ Работа с файлами соответствия артикулов и баркодов
- ✅ Полная автоматизация процесса обновления

## Требования

- Python 3.7+
- Ubuntu/Linux (скрипт адаптирован для `/home/rinat/wildberries/`)
- Доступ к почте Mail.ru (IMAP)
- API токен Wildberries

## Установка

### 1. Клонирование репозитория

```bash
# Клонируйте репозиторий
git clone https://github.com/SpiritWalker84/WB_scripts.git
cd WB_scripts
```

### 2. Установка зависимостей

```bash
# Создайте виртуальное окружение (рекомендуется)
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 3. Настройка конфигурации

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
nano .env
```

Заполните необходимые переменные:

```env
# IMAP настройки
IMAP_SERVER=imap.mail.ru
IMAP_PORT=993
IMAP_LOGIN=your_email@list.ru
IMAP_PASSWORD=your_password

# Настройки поиска письма
EMAIL_FROM=post@mx.forum-auto.ru
ATTACHMENT_FILENAME=FORUM-AUTO_PRICE.zip

# Пути (для Ubuntu)
BASE_DIR=/home/rinat/wildberries
DOWNLOAD_DIR=/home/rinat/wildberries/tmp
TARGET_DIR=/home/rinat/wildberries/price

# Wildberries API ключ
WB_API_TOKEN=your_wb_api_token
```

### 4. Подготовка файлов соответствия

Поместите в директорию проекта файлы:
- `*Артикулы*.xlsx` - файл с артикулами продавца и nmID
- `*Баркоды*.xlsx` - файл с баркодами и nmID

## Использование

### Полный цикл обновления (рекомендуется)

```bash
python3 run_full_update.py
```

Этот скрипт выполнит последовательно:
1. Удаление остатков с Wildberries
2. Загрузку прайсов и разбиение по брендам
3. Обновление цен и остатков

### Отдельные скрипты

#### 1. Удаление остатков

```bash
python3 clear_wb_stocks.py
```

#### 2. Загрузка прайсов

```bash
python3 download_price.py
```

#### 3. Обновление цен и остатков

```bash
python3 update_wb_stocks_prices.py
```

### Проверка готовности системы

```bash
python3 check_setup_price.py
```

## Структура проекта

```
wb_full/
├── clear_wb_stocks.py          # Удаление остатков
├── download_price.py            # Загрузка прайсов
├── update_wb_stocks_prices.py   # Обновление цен и остатков
├── run_full_update.py          # Единый скрипт для всех операций
├── check_setup_price.py        # Проверка готовности системы
├── requirements.txt            # Зависимости Python
├── .env.example                # Пример конфигурации
└── README.md                   # Документация
```

## Настройка брендов

По умолчанию обрабатываются бренды: BOSCH, TRIALLI, MANN

Для изменения списка брендов отредактируйте в `update_wb_stocks_prices.py`:

```python
BRANDS: List[str] = ['BOSCH', 'TRIALLI', 'MANN']
```

## Настройка коэффициента цены

По умолчанию цена повышается на 50% (коэффициент 1.5)

Для изменения отредактируйте в `update_wb_stocks_prices.py`:

```python
PRICE_MULTIPLIER: float = 1.5
```

## Структура файлов брендов

Файлы брендов должны находиться в `TARGET_DIR` и иметь формат:
- `brand_BOSCH.csv`
- `brand_TRIALLI.csv`
- `brand_MANN.csv`

Структура CSV:
- Колонка A (0) - бренд
- Колонка B (1) - артикул продавца или название
- Колонка C (2) - баркод или другой идентификатор
- Колонка D (3) - цена
- Колонка E (4) - количество

## Запуск как служба (systemd)

Создайте файл `/etc/systemd/system/wb-update.service`:

```ini
[Unit]
Description=Wildberries Full Update Service
After=network.target

[Service]
Type=oneshot
User=rinat
WorkingDirectory=/home/rinat/wildberries/wb_full
ExecStart=/home/rinat/wildberries/wb_full/venv/bin/python /home/rinat/wildberries/wb_full/run_full_update.py
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Для периодического запуска создайте таймер:

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
sudo systemctl enable wb-update.service
sudo systemctl enable wb-update.timer
sudo systemctl start wb-update.timer
```

## Безопасность

⚠️ **Важно:**
- Никогда не коммитьте файл `.env` в репозиторий
- Храните API токены в безопасности
- Используйте `.gitignore` для исключения чувствительных данных

## Устранение неполадок

### Ошибка подключения к IMAP
- Проверьте настройки в `.env`
- Убедитесь, что включен доступ по IMAP в настройках почты

### Ошибка API Wildberries
- Проверьте валидность `WB_API_TOKEN`
- Убедитесь, что токен не истек

### Файлы брендов не найдены
- Проверьте путь `TARGET_DIR` в `.env`
- Убедитесь, что файлы имеют правильные имена: `brand_<BRAND>.csv`

## Лицензия

MIT License

## Автор

SpiritWalker84

