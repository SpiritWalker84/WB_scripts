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
    Читает файлы соответствия артикулов и баркодов
    
    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]: 
            - Словарь {артикул_продавца: nmID}
            - Словарь {баркод: nmID}
            - Словарь {артикул_производителя: nmID} (если есть)
            - Словарь {баркод: chrtId} (если доступен)
    """
    print("Чтение файлов соответствия...")
    
    art_to_nmid: Dict[str, str] = {}
    barcode_to_nmid: Dict[str, str] = {}
    manufacturer_art_to_nmid: Dict[str, str] = {}  # Артикул производителя -> nmID
    barcode_to_chrtid: Dict[str, str] = {}
    
    # Ищем файл с артикулами
    art_file = None
    for file in os.listdir('.'):
        if 'Артикулы' in file and file.endswith('.xlsx'):
            art_file = file
            break
    
    if art_file:
        print(f"Читаю файл с артикулами: {art_file}")
        try:
            # Читаем файл, пропуская первые 4 строки (данные начинаются с 5-й строки, индекс 4)
            df_art = pd.read_excel(art_file, header=0, skiprows=4)
            
            # Структура (как в update_prices_stocks_wb.py):
            # Колонка B (индекс 1) - артикул производителя (каталожный номер)
            # Колонка C (индекс 2) - nmID (артикул WB)
            if len(df_art.columns) >= 3:
                art_col = df_art.columns[1]  # Колонка B - артикул производителя
                nmid_col = df_art.columns[2]  # Колонка C - nmID
                
                print(f"Использую колонку '{art_col}' (B) для артикула производителя")
                print(f"Использую колонку '{nmid_col}' (C) для nmID")
                
                for idx, row in df_art.iterrows():
                    try:
                        art = str(row[art_col]).strip()
                        nmid_val = row[nmid_col]
                        
                        # Пропускаем заголовки и пустые значения
                        if pd.isna(nmid_val) or str(art).lower() in ['артикул', 'артикул продавца', 'nan', '']:
                            continue
                        
                        nmid = str(int(float(nmid_val))).strip()
                        
                        if art and nmid and art != 'nan':
                            # Создаем соответствие артикул производителя -> nmID
                            # Убираем пробелы для сопоставления (AG 01007 -> AG01007)
                            art_clean = art.replace(' ', '').upper()
                            art_to_nmid[art_clean] = nmid
                            # Также сохраняем оригинальный вариант (на случай если в CSV есть пробелы)
                            art_to_nmid[art] = nmid
                    except (ValueError, TypeError, KeyError):
                        continue
                
                print(f"Загружено соответствий артикул->nmID: {len(art_to_nmid)}")
                if len(art_to_nmid) > 0:
                    # Показываем первые примеры для проверки
                    examples = list(art_to_nmid.items())[:3]
                    print(f"  Примеры: {examples}")
        except Exception as e:
            print(f"Ошибка при чтении файла артикулов: {e}")
    
    # Ищем файл с баркодами
    barcode_file = None
    for file in os.listdir('.'):
        if 'Баркоды' in file and file.endswith('.xlsx'):
            barcode_file = file
            break
    
    if barcode_file:
        print(f"Читаю файл с баркодами: {barcode_file}")
        try:
            # Читаем файл, пропуская первые 4 строки (данные начинаются с 5-й строки, индекс 4)
            df_barcode = pd.read_excel(barcode_file, header=0, skiprows=4)
            
            # Структура:
            # Колонка B (индекс 1) - артикул производителя (F00BH40270, AG 01007, CUK18000-2)
            # Колонка G (индекс 6) - баркод
            # Колонка C (индекс 2) - nmID
            if len(df_barcode.columns) >= 7:
                manufacturer_art_col = df_barcode.columns[1]  # Колонка B - артикул производителя
                barcode_col = df_barcode.columns[6]  # Колонка G - баркод
                
                print(f"Использую колонку '{manufacturer_art_col}' (B) для артикула производителя")
                print(f"Использую колонку '{barcode_col}' (G) для баркода")
                
                # Ищем колонку с nmID (колонка C)
                nmid_col = None
                if len(df_barcode.columns) > 2:
                    # Проверяем колонку C на наличие nmID
                    sample_val = df_barcode.iloc[0, 2] if len(df_barcode) > 0 else None
                    if sample_val and (isinstance(sample_val, (int, float)) or (isinstance(sample_val, str) and sample_val.strip().isdigit())):
                        nmid_col = df_barcode.columns[2]
                
                if nmid_col:
                    print(f"Использую колонку '{nmid_col}' (C) для nmID")
                else:
                    print("⚠ nmID будет получен через артикул продавца из файла артикулов")
                
                for idx, row in df_barcode.iterrows():
                    try:
                        barcode = str(row[barcode_col]).strip()
                        manufacturer_art = str(row[manufacturer_art_col]).strip() if len(row) > 1 else None
                        
                        # Пропускаем заголовки и пустые значения
                        if barcode.lower() in ['баркод', 'barcode', 'баркод в системе', 'nan', ''] or len(barcode) <= 5:
                            continue
                        
                        if manufacturer_art.lower() in ['артикул', 'артикул производителя', 'nan', ''] or not manufacturer_art:
                            continue
                        
                        nmid = None
                        
                        # Если есть колонка с nmID в файле баркодов
                        if nmid_col:
                            nmid_val = row[nmid_col]
                            if not pd.isna(nmid_val):
                                nmid = str(int(float(nmid_val))).strip()
                        
                        # Если nmID не найден, пробуем получить через артикул производителя из файла артикулов
                        # Но в файле артикулов нет артикула производителя, только артикул продавца
                        # Поэтому используем только nmID из файла баркодов
                        
                        if nmid:
                            barcode_to_nmid[barcode] = nmid
                            
                            # Создаем соответствие артикул производителя -> nmID
                            # Убираем пробелы для сопоставления (AG 01007 -> AG01007)
                            manufacturer_art_clean = manufacturer_art.replace(' ', '').upper()
                            manufacturer_art_to_nmid[manufacturer_art_clean] = nmid
                    except (ValueError, TypeError, KeyError):
                        continue
                
                print(f"Загружено соответствий баркод->nmID: {len(barcode_to_nmid)}")
                if len(barcode_to_nmid) > 0:
                    # Показываем первые примеры для проверки
                    examples = list(barcode_to_nmid.items())[:3]
                    print(f"  Примеры: {examples}")
        except Exception as e:
            print(f"Ошибка при чтении файла баркодов: {e}")
    
    return art_to_nmid, barcode_to_nmid, manufacturer_art_to_nmid, barcode_to_chrtid


def get_chrt_id_by_barcode(barcode: str, warehouse_id: int, stocks_cache: Optional[Dict[str, int]] = None) -> Optional[int]:
    """
    Получить chrtId по баркоду через API или из кэша
    
    Args:
        barcode: Баркод товара
        warehouse_id: ID склада
        stocks_cache: Кэш остатков {barcode: chrtId}
        
    Returns:
        Optional[int]: chrtId или None
    """
    # Сначала проверяем кэш
    if stocks_cache and barcode in stocks_cache:
        return stocks_cache[barcode]
    
    url = f"{Config.STOCKS_API_URL}/stocks/{warehouse_id}"
    headers = get_headers()
    params = {"sku": barcode}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        stocks = response.json()
        
        if stocks and len(stocks) > 0:
            chrt_id = stocks[0].get('chrtId')
            if chrt_id and stocks_cache is not None:
                stocks_cache[barcode] = chrt_id
            return chrt_id
    except requests.exceptions.RequestException:
        pass
    
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
        response = requests.put(url, headers=headers, json=payload)
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
    
    payload = {"data": prices_data}
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Ошибка при обновлении цен: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Ответ сервера: {e.response.text}")
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
    art_to_nmid, barcode_to_nmid, manufacturer_art_to_nmid, barcode_to_chrtid = read_mapping_files()
    
    if not art_to_nmid and not barcode_to_nmid:
        print("⚠ Предупреждение: не найдено файлов соответствия")
    
    # Обрабатываем каждый бренд
    print("\n3. Обрабатываю бренды...")
    
    all_stocks_data: Dict[int, List[Dict[str, Any]]] = {}  # {warehouse_id: [stocks]}
    all_prices_data: List[Dict[str, Any]] = []
    stocks_cache_by_warehouse: Dict[int, Dict[str, int]] = {}  # {warehouse_id: {barcode: chrtId}}
    
    # Инициализируем кэш остатков (будем заполнять по требованию)
    print("  Инициализация кэша остатков...")
    for warehouse in warehouses:
        warehouse_id = warehouse.get('id')
        stocks_cache_by_warehouse[warehouse_id] = {}
        print(f"    Склад {warehouse_id}: кэш готов (будет заполняться по требованию)")
    
    for brand in Config.BRANDS:
        print(f"\nБренд: {brand}")
        products = read_brand_file(brand)
        
        if not products:
            continue
        
        matched_count = 0
        unmatched_count = 0
        
        for product in products:
            nmid = None
            
            # Сначала пробуем найти nmID через артикул производителя (из CSV колонка B)
            # Логика как в update_prices_stocks_wb.py: артикул из CSV сопоставляется с art_to_nmid
            if product.get('manufacturer_art'):
                manufacturer_art = str(product['manufacturer_art']).strip()
                # Пробуем точное совпадение (с пробелами и без)
                if manufacturer_art in art_to_nmid:
                    nmid = art_to_nmid[manufacturer_art]
                else:
                    # Пробуем без пробелов и в верхнем регистре
                    manufacturer_art_clean = manufacturer_art.replace(' ', '').upper()
                    if manufacturer_art_clean in art_to_nmid:
                        nmid = art_to_nmid[manufacturer_art_clean]
                    else:
                        # Пробуем найти с учетом возможных различий
                        for art_key, art_nmid in art_to_nmid.items():
                            art_key_clean = str(art_key).strip().replace(' ', '').upper()
                            if art_key_clean == manufacturer_art_clean:
                                nmid = art_nmid
                                break
            
            # Если не нашли через артикул производителя, пробуем через баркод
            if not nmid and product.get('barcode'):
                barcode_clean = str(product['barcode']).strip().replace('-', '')
                # Пробуем как баркод (длинный числовой, 13+ цифр)
                if len(barcode_clean) >= 13 and barcode_clean.isdigit():
                    # Пробуем точное совпадение
                    if barcode_clean in barcode_to_nmid:
                        nmid = barcode_to_nmid[barcode_clean]
                    else:
                        # Пробуем найти с учетом возможных различий
                        for barcode_key, barcode_nmid in barcode_to_nmid.items():
                            if str(barcode_key).strip() == barcode_clean:
                                nmid = barcode_nmid
                                break
            
            # Если не нашли, пробуем через артикул продавца (числовой)
            if not nmid and product.get('seller_art'):
                seller_art_clean = str(product['seller_art']).strip()
                if seller_art_clean.isdigit():
                    if seller_art_clean in art_to_nmid:
                        nmid = art_to_nmid[seller_art_clean]
                    else:
                        for art_key, art_nmid in art_to_nmid.items():
                            if str(art_key).strip().lower() == seller_art_clean.lower():
                                nmid = art_nmid
                                break
            
            if not nmid:
                unmatched_count += 1
                # Выводим первые несколько примеров несовпадений для отладки
                if unmatched_count <= 3:
                    print(f"    ⚠ Не найдено соответствие: артикул_производителя={product.get('manufacturer_art')}, артикул_продавца={product.get('seller_art')}, баркод={product.get('barcode')}")
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
            # Нужно получить chrtId для каждого склада
            for warehouse in warehouses:
                warehouse_id = warehouse.get('id')
                
                if warehouse_id not in all_stocks_data:
                    all_stocks_data[warehouse_id] = []
                
                # Используем предзагруженный кэш
                stocks_cache = stocks_cache_by_warehouse.get(warehouse_id, {})
                
                # Получаем chrtId по баркоду из кэша или через API
                chrt_id = None
                if product['barcode']:
                    chrt_id = get_chrt_id_by_barcode(product['barcode'], warehouse_id, stocks_cache)
                
                if chrt_id:
                    all_stocks_data[warehouse_id].append({
                        "chrtId": chrt_id,
                        "sku": product['barcode'],
                        "amount": product['amount']
                    })
                elif product['barcode']:
                    # Если не удалось получить chrtId, пробуем использовать только sku
                    all_stocks_data[warehouse_id].append({
                        "sku": product['barcode'],
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
    
    # Обновляем остатки
    print("\n4. Обновляю остатки...")
    for warehouse_id, stocks_data in all_stocks_data.items():
        warehouse = next((w for w in warehouses if w.get('id') == warehouse_id), None)
        warehouse_name = warehouse.get('name', 'Неизвестный склад') if warehouse else 'Неизвестный склад'
        
        print(f"  Склад: {warehouse_name} (ID: {warehouse_id})")
        
        # Разбиваем на батчи по 100
        batch_size = 100
        for i in range(0, len(stocks_data), batch_size):
            batch = stocks_data[i:i + batch_size]
            print(f"    Батч {i//batch_size + 1} ({len(batch)} товаров)...")
            if update_stocks(warehouse_id, batch):
                print(f"    ✓ Обновлено остатков: {len(batch)}")
    
    # Обновляем цены
    print("\n5. Обновляю цены...")
    if all_prices_data:
        # Разбиваем на батчи по 100
        batch_size = 100
        for i in range(0, len(all_prices_data), batch_size):
            batch = all_prices_data[i:i + batch_size]
            print(f"  Батч {i//batch_size + 1} ({len(batch)} товаров)...")
            if update_prices(batch):
                print(f"  ✓ Обновлено цен: {len(batch)}")
    
    print("\n" + "=" * 60)
    print("Обновление завершено!")
    print("=" * 60)


if __name__ == "__main__":
    main()

