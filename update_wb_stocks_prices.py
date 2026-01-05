#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обновления остатков и цен товаров на Wildberries по брендам
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import csv
import re
import time
from datetime import datetime

# Загружаем переменные окружения
load_dotenv()


class Config:
    """Класс для хранения конфигурации из переменных окружения"""
    
    # API настройки
    WB_API_TOKEN: str = os.getenv('WB_API_TOKEN', '')
    STOCKS_API_URL: str = "https://marketplace-api.wildberries.ru/api/v3"
    PRICES_API_URL: str = "https://discounts-prices-api.wildberries.ru/api/v2"
    
    # Пути
    TARGET_DIR: Path = Path(os.getenv('TARGET_DIR', '/home/rinat/wildberries/price'))
    BASE_DIR: Path = Path(os.getenv('BASE_DIR', '/home/rinat/wildberries'))
    
    # Бренды для обработки
    BRANDS: List[str] = ['BOSCH', 'TRIALLI', 'MANN']
    
    # Коэффициент повышения цены
    PRICE_MULTIPLIER: float = 1.5
    
    @classmethod
    def validate(cls) -> None:
        """Проверяет, что все необходимые переменные окружения установлены"""
        if not cls.WB_API_TOKEN:
            raise ValueError("WB_API_TOKEN не установлен в .env файле")


def get_api_token() -> str:
    """
    Получить API токен из .env файла
    
    Returns:
        str: API токен Wildberries
        
    Raises:
        ValueError: Если токен не найден в .env файле
    """
    token = os.getenv('WB_API_TOKEN')
    if not token:
        token = os.getenv('WB_KEY')  # Для обратной совместимости
    
    if not token:
        raise ValueError(
            "API токен не найден в файле .env!\n"
            "Добавьте в .env файл строку: WB_API_TOKEN=ваш_токен"
        )
    
    return token


def get_headers() -> Dict[str, str]:
    """Получить заголовки для API запросов"""
    token = get_api_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_warehouses() -> List[Dict[str, Any]]:
    """Получить список складов продавца"""
    url = f"{Config.STOCKS_API_URL}/warehouses"
    headers = get_headers()
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    warehouses = response.json()
    print(f"Найдено складов: {len(warehouses)}")
    for warehouse in warehouses:
        print(f"  - {warehouse.get('name')} (ID: {warehouse.get('id')})")
    
    return warehouses


def read_mapping_files() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    Читает файл соответствия "Баркоды.xlsx"
    
    Структура файла (данные с 5-й строки):
    - Колонка B (индекс 1) - артикул производителя
    - Колонка C (индекс 2) - nmID (артикул WB)
    - Колонка G (индекс 6) - баркод
    
    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]: 
            - Словарь {артикул_производителя: nmID}
            - Словарь {баркод: nmID}
            - Словарь {артикул_производителя: nmID} (дубликат для совместимости)
            - Словарь {артикул_производителя: баркод}
            - Словарь {баркод: chrtId} (пустой, заполняется позже)
    """
    print("Чтение файла соответствия...")
    
    art_to_nmid: Dict[str, str] = {}  # Артикул производителя -> nmID
    barcode_to_nmid: Dict[str, str] = {}  # Баркод -> nmID
    manufacturer_art_to_nmid: Dict[str, str] = {}  # Артикул производителя -> nmID (дубликат)
    manufacturer_art_to_barcode: Dict[str, str] = {}  # Артикул производителя -> баркод
    barcode_to_chrtid: Dict[str, str] = {}
    
    # Ищем файл с баркодами
    barcode_file = None
    for file in os.listdir('.'):
        if 'Баркоды' in file and file.endswith('.xlsx'):
            barcode_file = file
            break
    
    if barcode_file:
        print(f"Читаю файл с баркодами: {barcode_file}")
        try:
            # Читаем файл, пропуская первые 4 строки (данные начинаются с 5-й строки)
            df_barcode = pd.read_excel(barcode_file, header=0, skiprows=4)
            
            # Структура файла (данные с 5-й строки):
            # Колонка B (индекс 1) - артикул производителя
            # Колонка C (индекс 2) - nmID (артикул WB)
            # Колонка G (индекс 6) - баркод
            if len(df_barcode.columns) >= 7:
                manufacturer_art_col = df_barcode.columns[1]  # Колонка B - артикул производителя
                nmid_col = df_barcode.columns[2]  # Колонка C - nmID
                barcode_col = df_barcode.columns[6]  # Колонка G - баркод
                
                print(f"Использую колонку '{manufacturer_art_col}' (B) для артикула производителя")
                print(f"Использую колонку '{nmid_col}' (C) для nmID")
                print(f"Использую колонку '{barcode_col}' (G) для баркода")
                
                for idx, row in df_barcode.iterrows():
                    try:
                        manufacturer_art = str(row[manufacturer_art_col]).strip() if len(row) > 1 else None
                        nmid_val = row[nmid_col]
                        barcode = str(row[barcode_col]).strip()
                        
                        # Пропускаем заголовки и пустые значения
                        if manufacturer_art.lower() in ['артикул', 'артикул производителя', 'nan', ''] or not manufacturer_art:
                            continue
                        
                        if pd.isna(nmid_val) or not barcode or barcode.lower() in ['баркод', 'barcode', 'баркод в системе', 'nan', ''] or len(barcode) <= 5:
                            continue
                        
                        # Получаем nmID из колонки C
                        try:
                            nmid = str(int(float(nmid_val))).strip()
                        except (ValueError, TypeError):
                            continue
                        
                        if nmid and barcode:
                            # Создаем соответствие артикул производителя -> nmID
                            # Сохраняем все варианты: оригинальный, без пробелов, нормализованный
                            manufacturer_art_clean = manufacturer_art.replace(' ', '').upper()
                            manufacturer_art_normalized = manufacturer_art_clean.replace('-', '').replace('/', '').replace('_', '')
                            
                            art_to_nmid[manufacturer_art] = nmid  # Оригинальный вариант
                            art_to_nmid[manufacturer_art_clean] = nmid  # Без пробелов
                            art_to_nmid[manufacturer_art_normalized] = nmid  # Нормализованный
                            manufacturer_art_to_nmid[manufacturer_art_clean] = nmid
                            
                            # Создаем соответствие баркод -> nmID
                            barcode_to_nmid[barcode] = nmid
                            
                            # Создаем соответствие артикул производителя -> баркод
                            manufacturer_art_to_barcode[manufacturer_art] = barcode  # Оригинальный вариант
                            manufacturer_art_to_barcode[manufacturer_art_clean] = barcode  # Без пробелов
                            manufacturer_art_to_barcode[manufacturer_art_normalized] = barcode  # Нормализованный
                    except (ValueError, TypeError, KeyError, IndexError):
                        continue
                
                print(f"Загружено соответствий артикул_производителя->nmID: {len(art_to_nmid)}")
                print(f"Загружено соответствий баркод->nmID: {len(barcode_to_nmid)}")
                print(f"Загружено соответствий артикул_производителя->баркод: {len(manufacturer_art_to_barcode)}")
                if len(art_to_nmid) > 0:
                    examples = list(art_to_nmid.items())[:3]
                    print(f"  Примеры артикул->nmID: {examples}")
                if len(barcode_to_nmid) > 0:
                    examples = list(barcode_to_nmid.items())[:3]
                    print(f"  Примеры баркод->nmID: {examples}")
                
                # Отладка: проверяем конкретные артикулы
                test_articles = ['PF 974', 'W610/6', '3397006952']
                print(f"\nОтладка: проверка конкретных артикулов:")
                for test_art in test_articles:
                    test_art_clean = test_art.replace(' ', '').upper()
                    found_nmid = None
                    found_barcode = None
                    
                    # Пробуем найти точное совпадение
                    if test_art in art_to_nmid:
                        found_nmid = art_to_nmid[test_art]
                    elif test_art_clean in art_to_nmid:
                        found_nmid = art_to_nmid[test_art_clean]
                    
                    if test_art in manufacturer_art_to_barcode:
                        found_barcode = manufacturer_art_to_barcode[test_art]
                    elif test_art_clean in manufacturer_art_to_barcode:
                        found_barcode = manufacturer_art_to_barcode[test_art_clean]
                    
                    if found_nmid:
                        print(f"  ✓ '{test_art}' -> nmID: {found_nmid}, баркод: {found_barcode or 'не найден'}")
                    else:
                        print(f"  ✗ '{test_art}' -> не найден в файле соответствия")
                        # Показываем похожие артикулы для отладки
                        similar = [k for k in art_to_nmid.keys() if test_art.upper() in str(k).upper() or str(k).upper() in test_art.upper()]
                        if similar:
                            print(f"    Похожие артикулы: {similar[:3]}")
        except Exception as e:
            print(f"Ошибка при чтении файла баркодов: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠ Файл 'Баркоды.xlsx' не найден!")
    
    return art_to_nmid, barcode_to_nmid, manufacturer_art_to_nmid, manufacturer_art_to_barcode, barcode_to_chrtid


def get_chrt_id_by_barcode(barcode: str, warehouse_id: int, stocks_cache: Optional[Dict[str, int]] = None) -> Optional[int]:
    """
    Получить chrtId по баркоду через API или из кэша
    
    Примечание: API может не поддерживать GET с параметром sku, поэтому возвращаем None.
    API сам найдет chrtId по sku при обновлении остатков через PUT запрос.
    
    Args:
        barcode: Баркод товара
        warehouse_id: ID склада
        stocks_cache: Кэш остатков {barcode: chrtId}
        
    Returns:
        Optional[int]: chrtId или None (API найдет автоматически)
    """
    # API не поддерживает получение chrtId через GET запрос с параметром sku
    # Возвращаем None - API сам найдет chrtId по sku при обновлении остатков
    return None


def get_all_stocks(warehouse_id: int) -> Dict[str, int]:
    """
    Получить все остатки со склада и создать кэш {barcode: chrtId}
    
    Примечание: API может не поддерживать получение всех остатков сразу,
    поэтому возвращаем пустой кэш и будем получать chrtId по требованию.
    
    Args:
        warehouse_id: ID склада
        
    Returns:
        Dict[str, int]: Словарь {barcode: chrtId} (обычно пустой)
    """
    # API не поддерживает GET /stocks/{warehouse_id} без параметров
    # Будем получать chrtId по требованию через параметр sku
    return {}


def read_brand_file(brand: str) -> List[Dict[str, Any]]:
    """
    Читает файл бренда и извлекает данные
    
    Args:
        brand: Название бренда
        
    Returns:
        List[Dict[str, Any]]: Список товаров с данными
    """
    brand_file = Config.TARGET_DIR / f"brand_{brand}.csv"
    
    if not brand_file.exists():
        print(f"  ⚠ Файл {brand_file} не найден")
        return []
    
    print(f"  Читаю файл: {brand_file}")
    
    products = []
    
    # Определяем кодировку и разделитель
    encoding = 'utf-8'
    try:
        with open(brand_file, 'r', encoding='utf-8') as f:
            sample = f.read(1000)
    except UnicodeDecodeError:
        encoding = 'cp1251'
        with open(brand_file, 'r', encoding='cp1251') as f:
            sample = f.read(1000)
    
    # Определяем разделитель
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=',;\t')
    except:
        dialect = csv.excel
    
    # Читаем файл
    with open(brand_file, 'r', encoding=encoding) as f:
        reader = csv.reader(f, dialect=dialect)
        
        header = None
        for row_num, row in enumerate(reader):
            if row_num == 0:
                header = row
                continue
            
            if len(row) < 5:
                continue
            
            # Структура файла бренда:
            # Колонка A (0) - бренд
            # Колонка B (1) - возможно артикул продавца или название
            # Колонка C (2) - возможно баркод или другой идентификатор
            # Колонка D (3) - цена
            # Колонка E (4) - количество
            
            try:
                # Извлекаем цену из колонки D (индекс 3)
                price_str = str(row[3]).strip().replace(',', '.').replace(' ', '').replace('"', '')
                # Извлекаем количество из колонки E (индекс 4)
                amount_str = str(row[4]).strip().replace(',', '.').replace(' ', '').replace('"', '')
                
                price = None
                amount = None
                
                if price_str and price_str.lower() not in ['nan', '', 'цена', 'price']:
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass
                
                if amount_str and amount_str.lower() not in ['nan', '', 'количество', 'amount', 'остаток']:
                    try:
                        amount = int(float(amount_str))
                    except ValueError:
                        pass
                
                if price is None or amount is None:
                    continue
                
                # Ищем артикул производителя и баркод
                # В CSV файлах колонка B (индекс 1) содержит артикул производителя (F00BH40270, AG 01007, CUK18000-2)
                # Колонка C (индекс 2) содержит описание товара
                manufacturer_art = None  # Артикул производителя из CSV
                seller_art = None  # Артикул продавца (будет найден через соответствие)
                barcode = None
                
                # Колонка B (индекс 1) - это артикул производителя
                if len(row) > 1 and row[1]:
                    potential_manufacturer_art = str(row[1]).strip().replace('"', '').replace("'", '')
                    # Пропускаем заголовки
                    if (potential_manufacturer_art.lower() not in ['бренд', 'brand', 'артикул', 'артикул продавца', 'название', 'name', 'nan', '', 'none'] and
                        len(potential_manufacturer_art) >= 2 and len(potential_manufacturer_art) <= 20):
                        # Убираем пробелы для сопоставления (AG 01007 -> AG01007)
                        manufacturer_art = potential_manufacturer_art.replace(' ', '')
                
                # Проверяем колонку C (индекс 2) на наличие баркода (маловероятно, но проверим)
                if len(row) > 2 and row[2]:
                    potential_barcode = str(row[2]).strip().replace('"', '').replace("'", '').replace(' ', '').replace('-', '')
                    # Если это длинный баркод (13+ цифр) - EAN-13
                    if len(potential_barcode) >= 13 and potential_barcode.isdigit():
                        barcode = potential_barcode
                
                products.append({
                    'manufacturer_art': manufacturer_art,  # Артикул производителя из CSV
                    'seller_art': seller_art,  # Артикул продавца (будет найден через соответствие)
                    'barcode': barcode,
                    'price': price,
                    'amount': amount,
                    'row': row
                })
            except (ValueError, IndexError, TypeError) as e:
                continue
    
    print(f"  Найдено товаров: {len(products)}")
    if products:
        first_product = products[0]
        print(f"  Пример: цена={first_product['price']}, количество={first_product['amount']}")
        print(f"    артикул_производителя={first_product.get('manufacturer_art', 'не найден')}, артикул_продавца={first_product.get('seller_art', 'не найден')}, баркод={first_product.get('barcode', 'не найден')}")
        # Показываем первые несколько строк для отладки
        if len(products) > 0:
            print(f"  Отладка: первые 3 строки CSV:")
            for i, p in enumerate(products[:3]):
                row_data = p.get('row', [])
                row_preview = [str(x)[:30] for x in row_data[:5]] if row_data else []
                print(f"    Строка {i+1}: {row_preview}")
    return products


def update_stocks(warehouse_id: int, stocks_data: List[Dict[str, Any]]) -> bool:
    """
    Обновить остатки на складе
    
    Args:
        warehouse_id: ID склада
        stocks_data: Список данных об остатках [{"chrtId": int, "sku": str, "amount": int}]
        
    Returns:
        bool: True если успешно
    """
    url = f"{Config.STOCKS_API_URL}/stocks/{warehouse_id}"
    headers = get_headers()
    
    payload = {"stocks": stocks_data}
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=60)
        
        # Обрабатываем 429 ошибку (Too Many Requests)
        if response.status_code == 429:
            print(f"    ⚠ Превышен лимит запросов (429), ожидание 5 секунд...")
            time.sleep(5)
            # Повторяем запрос после задержки
            response = requests.put(url, headers=headers, json=payload, timeout=60)
        
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Ошибка при обновлении остатков: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Ответ сервера: {e.response.text}")
        return False


def update_prices(prices_data: List[Dict[str, Any]]) -> bool:
    """
    Обновить цены товаров
    
    Args:
        prices_data: Список данных о ценах [{"nmID": int, "price": int, "discount": int}]
        
    Returns:
        bool: True если успешно
    """
    url = f"{Config.PRICES_API_URL}/upload/task"
    headers = get_headers()
    
    # Формируем данные в правильном формате (как в update_prices_stocks_wb.py)
    data_items = []
    for item in prices_data:
        nmid = item.get("nmID") or item.get("nmId")
        if nmid:
            data_items.append({
                "nmID": int(nmid),
                "price": int(item["price"]),
                "discount": int(item.get("discount", 0))
            })
    
    payload = {"data": data_items}
    
    try:
        # API требует POST, а не PUT
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        # Обрабатываем 429 ошибку (Too Many Requests)
        if response.status_code == 429:
            print(f"    ⚠ Превышен лимит запросов (429), ожидание 5 секунд...")
            time.sleep(5)
            # Повторяем запрос после задержки
            response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        # Обрабатываем 400 ошибку "prices already set" - это не критично
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_text = error_data.get('errorText', '')
                if 'already set' in error_text.lower() or 'уже установлены' in error_text.lower():
                    # Цены уже установлены - это нормально, не считаем ошибкой
                    print(f"    ℹ Цены уже установлены (не требуют обновления)")
                    return True
            except (ValueError, KeyError):
                pass
        
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Ошибка при обновлении цен: {e}")
        if hasattr(e, 'response') and e.response is not None:
            error_text = e.response.text
            print(f"    Ответ сервера: {error_text}")
            # Проверяем, не является ли это ошибкой "already set"
            if 'already set' in error_text.lower() or 'уже установлены' in error_text.lower():
                # Цены уже установлены - это нормально
                return True
        return False


def main() -> None:
    """Основная функция"""
    print("=" * 60)
    print("ОБНОВЛЕНИЕ ОСТАТКОВ И ЦЕН НА WILDBERRIES")
    print("=" * 60)
    
    try:
        Config.validate()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        return
    
    # Получаем список складов
    print("\n1. Получаю список складов...")
    try:
        warehouses = get_warehouses()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении списка складов: {e}")
        return
    
    if not warehouses:
        print("Ошибка: не найдено складов")
        return
    
    # Читаем файлы соответствия
    print("\n2. Читаю файлы соответствия...")
    art_to_nmid, barcode_to_nmid, manufacturer_art_to_nmid, manufacturer_art_to_barcode, barcode_to_chrtid = read_mapping_files()
    
    if not art_to_nmid and not barcode_to_nmid:
        print("⚠ Предупреждение: не найдено файлов соответствия")
    
    # Обрабатываем каждый бренд
    print("\n3. Обрабатываю бренды...")
    
    all_stocks_data: Dict[int, List[Dict[str, Any]]] = {}  # {warehouse_id: [stocks]}
    all_prices_data: List[Dict[str, Any]] = []
    
    for brand in Config.BRANDS:
        print(f"\nБренд: {brand}")
        products = read_brand_file(brand)
        
        if not products:
            continue
        
        matched_count = 0
        unmatched_count = 0
        
        for product in products:
            nmid = None
            
            # Проверяем только артикулы, которые есть в файле "Баркоды.xlsx"
            # Если артикула нет в файле соответствия, пропускаем товар
            if not product.get('manufacturer_art'):
                unmatched_count += 1
                continue
            
            manufacturer_art = str(product['manufacturer_art']).strip()
            manufacturer_art_clean = manufacturer_art.replace(' ', '').upper()
            manufacturer_art_normalized = manufacturer_art_clean.replace('-', '').replace('/', '').replace('_', '')
            
            # Проверяем, есть ли артикул в файле соответствия
            art_found = False
            if manufacturer_art in art_to_nmid:
                nmid = art_to_nmid[manufacturer_art]
                art_found = True
            elif manufacturer_art_clean in art_to_nmid:
                nmid = art_to_nmid[manufacturer_art_clean]
                art_found = True
            else:
                # Пробуем найти с учетом нормализации (убираем дефисы, слэши и т.д.)
                for art_key, art_nmid in art_to_nmid.items():
                    art_key_normalized = str(art_key).strip().replace(' ', '').upper().replace('-', '').replace('/', '').replace('_', '')
                    if art_key_normalized == manufacturer_art_normalized:
                        nmid = art_nmid
                        art_found = True
                        break
            
            # Если артикул не найден в файле соответствия, пропускаем товар
            # (это означает, что карточка еще не создана на WB)
            if not art_found:
                unmatched_count += 1
                # Выводим первые несколько примеров для информации
                if unmatched_count <= 5:
                    print(f"    ⚠ Пропущен (нет в файле соответствия): артикул={manufacturer_art}")
                continue
            
            matched_count += 1
            
            # Подготавливаем данные для обновления цен
            new_price = int(product['price'] * Config.PRICE_MULTIPLIER)
            all_prices_data.append({
                "nmID": int(nmid),
                "price": new_price,
                "discount": 0
            })
            
            # Подготавливаем данные для обновления остатков
            # Обновляем остатки только на складе 1619436
            TARGET_WAREHOUSE_ID = 1619436
            
            if TARGET_WAREHOUSE_ID not in all_stocks_data:
                all_stocks_data[TARGET_WAREHOUSE_ID] = []
            
            # Получаем баркод для обновления остатков из файла соответствия (колонка G)
            # Баркод всегда берем из файла "Баркоды.xlsx", так как артикул уже проверен
            barcode_for_stock = None
            if manufacturer_art in manufacturer_art_to_barcode:
                barcode_for_stock = manufacturer_art_to_barcode[manufacturer_art]
            elif manufacturer_art_clean in manufacturer_art_to_barcode:
                barcode_for_stock = manufacturer_art_to_barcode[manufacturer_art_clean]
            else:
                # Пробуем нормализованный вариант
                for art_key, barcode_val in manufacturer_art_to_barcode.items():
                    art_key_normalized = str(art_key).strip().replace(' ', '').upper().replace('-', '').replace('/', '').replace('_', '')
                    if art_key_normalized == manufacturer_art_normalized:
                        barcode_for_stock = barcode_val
                        break
            
            if barcode_for_stock:
                # Используем только sku - API сам найдет chrtId по sku при обновлении остатков
                # Это соответствует логике из update_prices_stocks_wb.py
                all_stocks_data[TARGET_WAREHOUSE_ID].append({
                    "sku": barcode_for_stock,
                    "amount": product['amount']
                })
        
        print(f"  Обработано товаров: {len(products)}")
        print(f"  Найдено соответствий: {matched_count}")
        if unmatched_count > 0:
            print(f"  Не найдено соответствий: {unmatched_count}")
            if unmatched_count > 3:
                print(f"    (показаны только первые 3 примера)")
    
    if not all_stocks_data and not all_prices_data:
        print("\n⚠ Не найдено данных для обновления")
        return
    
    # Подтверждение
    print("\n" + "=" * 60)
    print("ВНИМАНИЕ! Будет обновлено:")
    total_stocks = sum(len(stocks) for stocks in all_stocks_data.values())
    print(f"  - Остатков: {total_stocks}")
    print(f"  - Цен: {len(all_prices_data)}")
    print("=" * 60)
    confirm = input("\nПродолжить обновление? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y', 'да', 'д']:
        print("Операция отменена.")
        return
    
    # Обновляем остатки только на складе 1619436
    print("\n4. Обновляю остатки...")
    TARGET_WAREHOUSE_ID = 1619436
    
    if TARGET_WAREHOUSE_ID in all_stocks_data:
        stocks_data = all_stocks_data[TARGET_WAREHOUSE_ID]
        warehouse = next((w for w in warehouses if w.get('id') == TARGET_WAREHOUSE_ID), None)
        warehouse_name = warehouse.get('name', 'Неизвестный склад') if warehouse else 'Неизвестный склад'
        
        print(f"  Склад: {warehouse_name} (ID: {TARGET_WAREHOUSE_ID})")
        
        # Разбиваем на батчи по 100
        batch_size = 100
        for i in range(0, len(stocks_data), batch_size):
            batch = stocks_data[i:i + batch_size]
            batch_num = i//batch_size + 1
            print(f"    Батч {batch_num} ({len(batch)} товаров)...")
            if update_stocks(TARGET_WAREHOUSE_ID, batch):
                print(f"    ✓ Обновлено остатков: {len(batch)}")
            else:
                # Если ошибка, делаем задержку перед следующим батчем
                if i + batch_size < len(stocks_data):
                    print(f"    ⚠ Задержка 3 секунды перед следующим батчем...")
                    time.sleep(3)
            
            # Добавляем небольшую задержку между батчами для избежания 429 ошибок
            if i + batch_size < len(stocks_data):
                time.sleep(0.5)
    else:
        print(f"  ⚠ Нет данных для обновления остатков на складе {TARGET_WAREHOUSE_ID}")
    
    # Обновляем цены
    print("\n5. Обновляю цены...")
    if all_prices_data:
        # Разбиваем на батчи по 100
        batch_size = 100
        for i in range(0, len(all_prices_data), batch_size):
            batch = all_prices_data[i:i + batch_size]
            batch_num = i//batch_size + 1
            print(f"  Батч {batch_num} ({len(batch)} товаров)...")
            if update_prices(batch):
                print(f"  ✓ Обновлено цен: {len(batch)}")
            else:
                # Если ошибка, делаем задержку перед следующим батчем
                if i + batch_size < len(all_prices_data):
                    print(f"  ⚠ Задержка 3 секунды перед следующим батчем...")
                    time.sleep(3)
            
            # Добавляем небольшую задержку между батчами для избежания 429 ошибок
            if i + batch_size < len(all_prices_data):
                time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("Обновление завершено!")
    print("=" * 60)


if __name__ == "__main__":
    main()

