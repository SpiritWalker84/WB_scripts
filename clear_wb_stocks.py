"""
Скрипт для обнуления остатков товаров на Wildberries
"""
import os
import requests
import pandas as pd
from dotenv import load_dotenv
from typing import List, Dict, Any

# Загружаем переменные окружения
load_dotenv()

# API базовый URL
BASE_URL = "https://marketplace-api.wildberries.ru/api/v3"

def get_api_token() -> str:
    """
    Получить API токен из .env файла
    
    Returns:
        str: API токен Wildberries
        
    Raises:
        ValueError: Если токен не найден в .env файле
    """
    # Пробуем получить токен из переменной WB_API_TOKEN
    token = os.getenv('WB_API_TOKEN')
    
    # Если не найден, пробуем WB_KEY (для обратной совместимости)
    if not token:
        token = os.getenv('WB_KEY')
    
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
    url = f"{BASE_URL}/warehouses"
    headers = get_headers()
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    warehouses = response.json()
    print(f"Найдено складов: {len(warehouses)}")
    for warehouse in warehouses:
        print(f"  - {warehouse.get('name')} (ID: {warehouse.get('id')})")
    
    return warehouses

def read_products_data() -> Dict[str, List[str]]:
    """Прочитать данные о товарах из xlsx файлов"""
    products = {
        'nmIDs': [],
        'barcodes': []
    }
    
    # Читаем файл с артикулами (nmID)
    art_file = None
    for file in os.listdir('.'):
        if 'Артикулы' in file and file.endswith('.xlsx'):
            art_file = file
            break
    
    if art_file:
        print(f"Читаю файл с артикулами: {art_file}")
        df_art = pd.read_excel(art_file, header=0)
        
        # Читаем nmID из колонки C (индекс 2) - "Артикул продавца"
        if len(df_art.columns) > 2:
            col_nmid = df_art.columns[2]  # Колонка C
            print(f"Использую колонку '{col_nmid}' для nmID")
            
            # Пропускаем заголовки (первые строки могут содержать текст)
            values = df_art[col_nmid].dropna()
            # Фильтруем только числовые значения (nmID - это числа)
            nm_ids = []
            for val in values:
                try:
                    # Пробуем преобразовать в число
                    nm_id = int(float(val))
                    nm_ids.append(str(nm_id))
                except (ValueError, TypeError):
                    # Пропускаем нечисловые значения (заголовки)
                    continue
            products['nmIDs'] = nm_ids
            print(f"Найдено артикулов (nmID): {len(products['nmIDs'])}")
            if len(products['nmIDs']) > 0:
                print(f"  Примеры: {products['nmIDs'][:5]}")
        else:
            print("Ошибка: файл с артикулами не содержит колонку C")
    
    # Читаем файл с баркодами
    barcode_file = None
    for file in os.listdir('.'):
        if 'Баркоды' in file and file.endswith('.xlsx'):
            barcode_file = file
            break
    
    if barcode_file:
        print(f"Читаю файл с баркодами: {barcode_file}")
        df_barcode = pd.read_excel(barcode_file, header=0)
        
        # Читаем баркоды из колонки G (индекс 6)
        if len(df_barcode.columns) > 6:
            col_barcode = df_barcode.columns[6]  # Колонка G
            print(f"Использую колонку '{col_barcode}' для баркодов")
            
            # Пропускаем заголовки
            values = df_barcode[col_barcode].dropna()
            # Фильтруем только строковые значения, которые выглядят как баркоды
            barcodes = []
            for val in values:
                val_str = str(val).strip()
                # Пропускаем заголовки (текстовые значения)
                if val_str.lower() not in ['баркод', 'barcode', 'баркод в системе', ''] and len(val_str) > 5:
                    barcodes.append(val_str)
            products['barcodes'] = barcodes
            print(f"Найдено баркодов: {len(products['barcodes'])}")
            if len(products['barcodes']) > 0:
                print(f"  Примеры: {products['barcodes'][:5]}")
        else:
            print("Ошибка: файл с баркодами не содержит колонку G")
    
    return products

def clear_stocks_by_barcodes(warehouse_id: int, barcodes: List[str]) -> bool:
    """Обнулить остатки по баркодам (установить amount: 0)"""
    url = f"{BASE_URL}/stocks/{warehouse_id}"
    headers = get_headers()
    
    # Создаем запрос для обнуления остатков
    stocks = [{"sku": barcode, "amount": 0} for barcode in barcodes]
    
    payload = {"stocks": stocks}
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"  ✓ Обнулено остатков по баркодам: {len(barcodes)}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Ошибка при обнулении остатков по баркодам: {e}")
        if hasattr(e.response, 'text'):
            print(f"    Ответ сервера: {e.response.text}")
        return False

def delete_stocks_by_barcodes(warehouse_id: int, barcodes: List[str]) -> bool:
    """Удалить остатки по баркодам"""
    url = f"{BASE_URL}/stocks/{warehouse_id}"
    headers = get_headers()
    
    payload = {"skus": barcodes}
    
    try:
        response = requests.delete(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"  ✓ Удалено остатков по баркодам: {len(barcodes)}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Ошибка при удалении остатков по баркодам: {e}")
        if hasattr(e.response, 'text'):
            print(f"    Ответ сервера: {e.response.text}")
        return False

def clear_all_stocks():
    """Основная функция для обнуления всех остатков"""
    print("=" * 60)
    print("Начинаю обнуление остатков на Wildberries")
    print("=" * 60)
    
    # Получаем список складов
    print("\n1. Получаю список складов...")
    try:
        warehouses = get_warehouses()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении списка складов: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Ответ сервера: {e.response.text}")
        return
    
    if not warehouses:
        print("Ошибка: не найдено складов")
        return
    
    # Читаем данные о товарах
    print("\n2. Читаю данные о товарах из xlsx файлов...")
    products = read_products_data()
    
    if not products['barcodes'] and not products['nmIDs']:
        print("Ошибка: не найдено данных о товарах")
        return
    
    # Подтверждение перед обнулением
    print("\n" + "=" * 60)
    print("ВНИМАНИЕ! Будет обнулено остатков:")
    print(f"  - Товаров: {len(products['barcodes']) if products['barcodes'] else len(products['nmIDs'])}")
    print(f"  - Складов: {len(warehouses)}")
    print("=" * 60)
    confirm = input("\nПродолжить обнуление остатков? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y', 'да', 'д']:
        print("Операция отменена.")
        return
    
    # Обнуляем остатки на каждом складе
    print("\n3. Обнуляю остатки на складах...")
    
    for warehouse in warehouses:
        warehouse_id = warehouse.get('id')
        warehouse_name = warehouse.get('name', 'Неизвестный склад')
        
        print(f"\nСклад: {warehouse_name} (ID: {warehouse_id})")
        
        # Используем баркоды для обнуления (если они есть)
        if products['barcodes']:
            # Разбиваем на батчи, чтобы не перегружать API
            batch_size = 100
            for i in range(0, len(products['barcodes']), batch_size):
                batch = products['barcodes'][i:i + batch_size]
                print(f"  Обрабатываю батч {i//batch_size + 1} ({len(batch)} товаров)...")
                clear_stocks_by_barcodes(warehouse_id, batch)
        
        # Если нет баркодов, но есть nmID, можно попробовать использовать их
        # Но для этого нужен chrtId, который получается из nmID через другой API
        # Пока оставим только работу с баркодами
    
    print("\n" + "=" * 60)
    print("Обнуление остатков завершено!")
    print("=" * 60)

if __name__ == "__main__":
    clear_all_stocks()

