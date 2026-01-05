# Инструкция по клонированию репозитория

## ❌ Неправильно

```bash
git clone https://github.com/SpiritWalker84/sysadmin_repo/tree/main/wb_full
```

Git не поддерживает клонирование отдельных директорий через HTTPS.

## ✅ Правильно

### Вариант 1: Клонировать весь репозиторий (рекомендуется)

```bash
# Клонируйте весь репозиторий
git clone https://github.com/SpiritWalker84/sysadmin_repo.git

# Перейдите в директорию wb_full
cd sysadmin_repo/wb_full
```

### Вариант 2: Клонировать только нужную директорию (sparse checkout)

```bash
# Создайте пустой репозиторий
mkdir sysadmin_repo
cd sysadmin_repo
git init

# Добавьте remote
git remote add origin https://github.com/SpiritWalker84/sysadmin_repo.git

# Включите sparse checkout
git config core.sparseCheckout true

# Укажите нужную директорию
echo "wb_full/*" > .git/info/sparse-checkout

# Получите файлы
git pull origin main
```

### Вариант 3: Использовать GitHub CLI (если установлен)

```bash
gh repo clone SpiritWalker84/sysadmin_repo
cd sysadmin_repo/wb_full
```

## После клонирования

```bash
# Перейдите в директорию wb_full
cd sysadmin_repo/wb_full

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Создайте .env файл
cp .env.example .env
nano .env

# Проверьте готовность
python3 check_setup_price.py
```

