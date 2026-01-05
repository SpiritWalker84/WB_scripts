# Инструкция по выгрузке в репозиторий

## Подготовка к коммиту

### 1. Проверка файлов

Убедитесь, что следующие файлы НЕ будут закоммичены (должны быть в `.gitignore`):
- `.env`
- `wb_key.txt`
- `venv/`
- `__pycache__/`

**Примечание:** Файлы с данными (`*.xlsx`, `*.csv`) включены в репозиторий для удобства работы.

### 2. Структура для коммита

```
wb_full/
├── .gitignore
├── .env.example
├── README.md
├── DEPLOYMENT.md
├── GIT_DEPLOY_INSTRUCTIONS.md
├── clear_wb_stocks.py
├── download_price.py
├── update_wb_stocks_prices.py
├── run_full_update.py
├── check_setup_price.py
└── requirements.txt
```

## Команды для Git

### Первоначальная настройка (если репозиторий еще не клонирован)

```bash
# Клонируйте репозиторий
git clone https://github.com/SpiritWalker84/sysadmin_repo.git
cd sysadmin_repo

# Создайте ветку для wb_full (опционально)
git checkout -b wb_full
```

### Добавление файлов

```bash
# Перейдите в корень репозитория
cd sysadmin_repo

# Добавьте директорию wb_full
git add wb_full/

# Проверьте, что будет закоммичено
git status

# Убедитесь, что .env и другие чувствительные файлы НЕ в списке
```

### Коммит

```bash
git commit -m "Add wb_full: Wildberries automation scripts

- Add clear_wb_stocks.py: Clear stocks on Wildberries
- Add download_price.py: Download and split prices by brands
- Add update_wb_stocks_prices.py: Update prices and stocks
- Add run_full_update.py: Unified script for full update cycle
- Add check_setup_price.py: System readiness check
- Add documentation and deployment instructions"
```

### Push в репозиторий

```bash
# Если это новая ветка
git push -u origin wb_full

# Или если работаете в main
git push origin main
```

## Проверка перед коммитом

### Проверка .gitignore

```bash
# Убедитесь, что .gitignore работает
git check-ignore -v .env
git check-ignore -v wb_key.txt
git check-ignore -v *.xlsx
```

### Просмотр изменений

```bash
# Посмотрите, что будет закоммичено
git status

# Посмотрите diff
git diff --cached
```

## Обновление существующего репозитория

Если директория `wb_full` уже существует в репозитории:

```bash
cd sysadmin_repo
git pull origin main
git add wb_full/
git commit -m "Update wb_full scripts"
git push origin main
```

## Создание Pull Request (если используете ветки)

```bash
# Создайте ветку
git checkout -b feature/wb_full_update

# Внесите изменения
# ...

# Закоммитьте
git add .
git commit -m "Update wb_full"

# Запушьте ветку
git push origin feature/wb_full_update
```

Затем создайте Pull Request через веб-интерфейс GitHub.

## Важные замечания

⚠️ **Безопасность:**
- Никогда не коммитьте `.env` файл
- Не коммитьте файлы с API токенами
- Не коммитьте файлы с данными (xlsx, csv с прайсами)

✅ **Рекомендуется:**
- Использовать `.env.example` для примера конфигурации
- Коммитить только код и документацию
- Использовать описательные сообщения коммитов

## Откат изменений (если что-то пошло не так)

```bash
# Отменить последний коммит (но сохранить изменения)
git reset --soft HEAD~1

# Полностью отменить последний коммит
git reset --hard HEAD~1

# Удалить файлы из индекса, но оставить в рабочей директории
git reset HEAD <file>
```

