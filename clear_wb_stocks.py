"""
Скрипт для обнуления остатков товаров на Wildberries
"""
import os
import requests
import pandas as pd
import time
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
        df_art = pd.read_excel(art_file, header=0)
        
        # Читаем nmID из колонки C (индекс 2) - "Артикул продавца"
        if len(df_art.columns) > 2:
            col_nmid = df_art.columns[2]  # Колонка C
            
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
        else:
            print("Ошибка: файл с артикулами не содержит колонку C")
    
    # Читаем файл с баркодами
    barcode_file = None
    for file in os.listdir('.'):
        if 'Баркоды' in file and file.endswith('.xlsx'):
            barcode_file = file
            break
    
    if barcode_file:
        df_barcode = pd.read_excel(barcode_file, header=0)
        
        # Читаем баркоды из колонки G (индекс 6)
        if len(df_barcode.columns) > 6:
            col_barcode = df_barcode.columns[6]  # Колонка G
            
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
        else:
            print("Ошибка: файл с баркодами не содержит колонку G")
    
    return products

def clear_stocks_by_barcodes(warehouse_id: int, barcodes: List[str], max_retries: int = 3) -> bool:
    """
    Обнулить остатки по баркодам (установить amount: 0)
    
    Args:
        warehouse_id: ID склада
        barcodes: Список баркодов
        max_retries: Максимальное количество попыток при ошибке 429
    """
    url = f"{BASE_URL}/stocks/{warehouse_id}"
    headers = get_headers()
    
    # Создаем запрос для обнуления остатков
    stocks = [{"sku": barcode, "amount": 0} for barcode in barcodes]
    
    payload = {"stocks": stocks}
    
    for attempt in range(max_retries):
        try:
            response = requests.put(url, headers=headers, json=payload, timeout=60)
            
            # Обрабатываем 429 ошибку (Too Many Requests)
            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)  # Увеличиваем задержку с каждой попыткой
                print(f"    ⚠ Превышен лимит запросов (429), ожидание {wait_time} секунд...")
                time.sleep(wait_time)
                # Повторяем запрос после задержки
                continue
            
            # Обрабатываем 409 ошибку (Conflict) - товары ODC/LCL не подходят для склада
            if response.status_code == 409:
                try:
                    error_data = response.json()
                    # Проверяем, является ли это ошибкой типа CargoWarehouseRestriction
                    if isinstance(error_data, list) and len(error_data) > 0:
                        error_code = error_data[0].get('code', '')
                        if 'CargoWarehouseRestriction' in error_code:
                            # Это не критичная ошибка - товары ODC/LCL не подходят для этого склада
                            # Пробуем обнулить товары по одному, чтобы обнулить те, которые можно
                            success_count = 0
                            for barcode in barcodes:
                                single_payload = {"stocks": [{"sku": barcode, "amount": 0}]}
                                try:
                                    single_response = requests.put(url, headers=headers, json=single_payload, timeout=60)
                                    if single_response.status_code == 200:
                                        success_count += 1
                                    elif single_response.status_code == 409:
                                        # Этот товар не подходит для склада - пропускаем
                                        continue
                                except:
                                    pass
                            # Возвращаем True даже если не все товары обнулились (ODC товары пропускаются)
                            return True
                except (ValueError, KeyError, IndexError):
                    pass
                # Если не удалось распарсить ошибку, продолжаем как обычно
            
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            # Проверяем, не является ли это ошибкой 409 с CargoWarehouseRestriction
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 409:
                    try:
                        error_data = e.response.json()
                        if isinstance(error_data, list) and len(error_data) > 0:
                            error_code = error_data[0].get('code', '')
                            if 'CargoWarehouseRestriction' in error_code:
                                # Это не критичная ошибка - товары ODC/LCL не подходят для склада
                                # Пробуем обнулить товары по одному
                                for barcode in barcodes:
                                    single_payload = {"stocks": [{"sku": barcode, "amount": 0}]}
                                    try:
                                        single_response = requests.put(url, headers=headers, json=single_payload, timeout=60)
                                        if single_response.status_code == 409:
                                            # Этот товар не подходит для склада - пропускаем
                                            continue
                                    except:
                                        pass
                                # Возвращаем True даже если не все товары обнулились (ODC товары пропускаются)
                                return True
                    except (ValueError, KeyError, IndexError):
                        pass
                
                # Если это последняя попытка и не 429, выводим ошибку только если это не 409 CargoWarehouseRestriction
                if attempt == max_retries - 1:
                    if e.response.status_code != 409:
                        print(f"  ✗ Ошибка при обнулении остатков по баркодам: {e}")
                        print(f"    Ответ сервера: {e.response.text}")
                    return False
                
                # Если не последняя попытка и это 429, продолжаем цикл
                if e.response.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    print(f"    ⚠ Превышен лимит запросов (429), ожидание {wait_time} секунд...")
                    time.sleep(wait_time)
                    continue
            
            # Для других ошибок на последней попытке выводим сообщение
            if attempt == max_retries - 1:
                print(f"  ✗ Ошибка при обнулении остатков по баркодам: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"    Ответ сервера: {e.response.text}")
                return False
    
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
    # Получаем список складов
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
    products = read_products_data()
    
    if not products['barcodes'] and not products['nmIDs']:
        print("Ошибка: не найдено данных о товарах")
        return
    
    # Исключаем склад 1620586 из обработки
    EXCLUDED_WAREHOUSE_ID = 1620586
    warehouses = [w for w in warehouses if w.get('id') != EXCLUDED_WAREHOUSE_ID]
    
    if not warehouses:
        print("Ошибка: не осталось складов для обработки после исключения")
        return
    
    # Обнуляем остатки на каждом складе
    print(f"Обнуляю остатки: {len(products['barcodes']) if products['barcodes'] else len(products['nmIDs'])} товаров на {len(warehouses)} складе(ах)...")
    
    for warehouse in warehouses:
        warehouse_id = warehouse.get('id')
        
        # Используем баркоды для обнуления (если они есть)
        if products['barcodes']:
            # Разбиваем на батчи, чтобы не перегружать API
            batch_size = 100
            total_batches = (len(products['barcodes']) + batch_size - 1) // batch_size
            for i in range(0, len(products['barcodes']), batch_size):
                batch = products['barcodes'][i:i + batch_size]
                batch_num = i//batch_size + 1
                # Показываем прогресс каждые 10 батчей или последний батч
                if batch_num % 10 == 0 or batch_num == total_batches:
                    print(f"  Обрабатываю батч {batch_num}/{total_batches}...")
                clear_stocks_by_barcodes(warehouse_id, batch)
                
                # Добавляем небольшую задержку между батчами для избежания 429 ошибок
                if i + batch_size < len(products['barcodes']):
                    time.sleep(0.5)
        
        # Если нет баркодов, но есть nmID, можно попробовать использовать их
        # Но для этого нужен chrtId, который получается из nmID через другой API
        # Пока оставим только работу с баркодами
    
    print("Обнуление остатков завершено!")

if __name__ == "__main__":
    clear_all_stocks()

