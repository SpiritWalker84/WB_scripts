#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки готовности системы для download_price.py
"""

import sys
from pathlib import Path
from typing import List, Tuple
from dotenv import load_dotenv
import os


# Загружаем переменные окружения из .env файла
load_dotenv()


def check_python_version() -> bool:
    """Проверяет версию Python"""
    print("Проверка версии Python...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} - требуется Python 3.7+")
        return False


def check_standard_libraries() -> bool:
    """Проверяет стандартные библиотеки, используемые в download_price.py"""
    print("\nПроверка стандартных библиотек...")
    libraries = [
        'imaplib', 'email', 'ssl', 'os', 'pathlib', 
        'zipfile', 'csv', 're'
    ]
    
    all_ok = True
    for lib in libraries:
        try:
            __import__(lib)
            print(f"  ✓ {lib} - OK")
        except ImportError:
            print(f"  ✗ {lib} - отсутствует")
            all_ok = False
    
    return all_ok


def check_third_party_libraries() -> bool:
    """Проверяет сторонние библиотеки"""
    print("\nПроверка сторонних библиотек...")
    libraries = ['dotenv']
    
    all_ok = True
    for lib in libraries:
        try:
            if lib == 'dotenv':
                __import__('dotenv')
            print(f"  ✓ {lib} - OK")
        except ImportError:
            print(f"  ✗ {lib} - отсутствует (установите: pip install python-dotenv)")
            all_ok = False
    
    return all_ok


def check_env_file() -> bool:
    """Проверяет наличие и корректность .env файла"""
    print("\nПроверка файла .env...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("  ✗ Файл .env не найден")
        print("  → Создайте файл .env на основе .env.example")
        return False
    
    print("  ✓ Файл .env найден")
    
    # Проверяем наличие обязательных переменных
    required_vars = [
        'IMAP_SERVER',
        'IMAP_PORT',
        'IMAP_LOGIN',
        'IMAP_PASSWORD',
        'EMAIL_FROM',
        'ATTACHMENT_FILENAME',
        'BASE_DIR',
        'DOWNLOAD_DIR',
        'TARGET_DIR'
    ]
    
    missing_vars: List[str] = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"  ✗ Отсутствуют обязательные переменные: {', '.join(missing_vars)}")
        return False
    
    print("  ✓ Все обязательные переменные установлены")
    
    # Проверяем, что пароль не пустой
    if os.getenv('IMAP_PASSWORD', '').strip() == '':
        print("  ⚠ IMAP_PASSWORD пустой - проверьте настройки")
        return False
    
    return True


def check_paths() -> bool:
    """Проверяет наличие необходимых путей"""
    print("\nПроверка путей...")
    
    base_dir = Path(os.getenv('BASE_DIR', '/home/rinat/wildberries'))
    download_dir = Path(os.getenv('DOWNLOAD_DIR', '/home/rinat/wildberries/tmp'))
    target_dir = Path(os.getenv('TARGET_DIR', '/home/rinat/wildberries/price'))
    
    paths: List[Tuple[Path, str]] = [
        (base_dir, "Базовая папка"),
        (download_dir, "Временная папка для архивов"),
        (target_dir, "Папка для прайс-файлов"),
    ]
    
    all_ok = True
    for path, description in paths:
        if path.exists():
            if path.is_dir():
                print(f"  ✓ {path} - существует ({description})")
            else:
                print(f"  ✗ {path} - существует, но это не папка")
                all_ok = False
        else:
            print(f"  ⚠ {path} - не существует (будет создана автоматически)")
            # Создаем папку
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"    → Создана")
            except Exception as e:
                print(f"    ✗ Ошибка создания: {e}")
                all_ok = False
    
    return all_ok


def check_project_file() -> bool:
    """Проверяет наличие файла проекта"""
    print("\nПроверка файла проекта...")
    file = "download_price.py"
    if Path(file).exists():
        print(f"  ✓ {file} - найден")
        return True
    else:
        print(f"  ✗ {file} - не найден")
        return False


def check_imap_settings() -> bool:
    """Проверяет настройки IMAP из .env файла"""
    print("\nПроверка настроек IMAP...")
    
    imap_server = os.getenv('IMAP_SERVER', '')
    imap_port = os.getenv('IMAP_PORT', '')
    imap_login = os.getenv('IMAP_LOGIN', '')
    imap_password = os.getenv('IMAP_PASSWORD', '')
    
    if not all([imap_server, imap_port, imap_login, imap_password]):
        print("  ✗ Не все настройки IMAP установлены в .env")
        return False
    
    print(f"  ✓ IMAP сервер: {imap_server}:{imap_port}")
    print(f"  ✓ IMAP логин: {imap_login}")
    print("  ⚠ Убедитесь, что логин и пароль актуальны")
    
    return True


def main() -> bool:
    """Основная функция"""
    print("=" * 60)
    print("ПРОВЕРКА ГОТОВНОСТИ СИСТЕМЫ ДЛЯ download_price.py")
    print("=" * 60)
    
    results: List[Tuple[str, bool]] = []
    results.append(("Версия Python", check_python_version()))
    results.append(("Стандартные библиотеки", check_standard_libraries()))
    results.append(("Сторонние библиотеки", check_third_party_libraries()))
    results.append(("Файл проекта", check_project_file()))
    results.append(("Файл .env", check_env_file()))
    results.append(("Настройки IMAP", check_imap_settings()))
    results.append(("Пути", check_paths()))
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ:")
    all_ok = True
    for name, result in results:
        status = "✓ OK" if result else "✗ ОШИБКА"
        print(f"  {name}: {status}")
        if not result:
            all_ok = False
    
    print("=" * 60)
    if all_ok:
        print("\n✓ Система готова к работе!")
        print("\nДля запуска выполните:")
        print("  python3 download_price.py")
    else:
        print("\n✗ Обнаружены проблемы. Исправьте их перед использованием.")
        print("\nРекомендации:")
        print("  1. Убедитесь, что файл .env существует и содержит все необходимые переменные")
        print("  2. Установите недостающие библиотеки: pip install -r requirements.txt")
        print("  3. Проверьте права доступа к папкам")
    
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
