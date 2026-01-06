#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый скрипт для полного обновления остатков и цен на Wildberries
Выполняет последовательно:
1. Удаление остатков с WB
2. Загрузка прайсов и разбиение по брендам
3. Обновление цен и остатков
"""

import sys
from pathlib import Path
from typing import Optional
import traceback
import time

# Импортируем функции из других скриптов
try:
    from clear_wb_stocks import clear_all_stocks
except ImportError as e:
    print(f"Ошибка импорта clear_wb_stocks: {e}")
    sys.exit(1)

try:
    from download_price import main as download_price_main
except ImportError as e:
    print(f"Ошибка импорта download_price: {e}")
    sys.exit(1)

try:
    from update_wb_stocks_prices import main as update_stocks_prices_main
except ImportError as e:
    print(f"Ошибка импорта update_wb_stocks_prices: {e}")
    sys.exit(1)


def run_step(step_num: int, step_name: str, step_func, *args, **kwargs) -> bool:
    """
    Выполняет шаг процесса с обработкой ошибок
    
    Args:
        step_num: Номер шага
        step_name: Название шага
        step_func: Функция для выполнения
        *args: Позиционные аргументы для функции
        **kwargs: Именованные аргументы для функции
        
    Returns:
        bool: True если шаг выполнен успешно, False в противном случае
    """
    print("\n" + "=" * 60)
    print(f"ШАГ {step_num}: {step_name}")
    print("=" * 60)
    
    try:
        # Сохраняем оригинальный sys.exit для перехвата
        original_exit = sys.exit
        
        def custom_exit(code=0):
            """Перехватывает sys.exit и преобразует в исключение"""
            if code != 0:
                raise SystemExit(code)
        
        sys.exit = custom_exit
        
        try:
            if args or kwargs:
                step_func(*args, **kwargs)
            else:
                step_func()
            print(f"\n✓ Шаг {step_num} выполнен успешно")
            return True
        finally:
            # Восстанавливаем оригинальный sys.exit
            sys.exit = original_exit
            
    except KeyboardInterrupt:
        print(f"\n⚠ Шаг {step_num} прерван пользователем")
        return False
    except SystemExit as e:
        if e.code != 0:
            print(f"\n✗ Шаг {step_num} завершился с ошибкой (код: {e.code})")
            return False
        return True
    except Exception as e:
        print(f"\n✗ Ошибка на шаге {step_num}: {e}")
        print("\nДетали ошибки:")
        traceback.print_exc()
        return False


def main() -> None:
    """Основная функция для выполнения полного цикла обновления"""
    print("=" * 60)
    print("ПОЛНОЕ ОБНОВЛЕНИЕ ОСТАТКОВ И ЦЕН НА WILDBERRIES")
    print("=" * 60)
    print("\nЭтот скрипт выполнит следующие операции:")
    print("  1. Удаление остатков с Wildberries")
    print("  2. Загрузка прайсов из почты и разбиение по брендам")
    print("  3. Обновление цен и остатков на Wildberries")
    print("\n" + "=" * 60)
    
    # Шаг 1: Удаление остатков
    if not run_step(1, "Удаление остатков с Wildberries", clear_all_stocks):
        print("\n⚠ Процесс остановлен на шаге 1")
        print("Продолжаю со следующего шага...")
    
    # Задержка 30 секунд после удаления остатков перед обновлением
    print("\n⏳ Ожидание 30 секунд после удаления остатков...")
    time.sleep(30)
    
    # Шаг 2: Загрузка прайсов
    if not run_step(2, "Загрузка прайсов и разбиение по брендам", download_price_main):
        print("\n⚠ Процесс остановлен на шаге 2")
        print("Продолжаю со следующего шага...")
    
    # Шаг 3: Обновление цен и остатков
    if not run_step(3, "Обновление цен и остатков", update_stocks_prices_main):
        print("\n⚠ Процесс остановлен на шаге 3")
        print("Процесс завершен с ошибками.")
        return
    
    # Финальное сообщение
    print("\n" + "=" * 60)
    print("✓ ВСЕ ШАГИ ВЫПОЛНЕНЫ УСПЕШНО!")
    print("=" * 60)
    print("\nПолный цикл обновления завершен:")
    print("  ✓ Остатки удалены")
    print("  ✓ Прайсы загружены и разбиты по брендам")
    print("  ✓ Цены и остатки обновлены на Wildberries")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Процесс прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)

