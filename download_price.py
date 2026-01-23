#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для скачивания, распаковки и разбиения прайс-листа по брендам из почты Mail.ru
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.message import Message
import ssl
import os
from pathlib import Path
import zipfile
import csv
import re
from datetime import datetime
from typing import Tuple, List, Dict, Optional, Any
from dotenv import load_dotenv


# Загружаем переменные окружения из .env файла
load_dotenv()


class Config:
    """Класс для хранения конфигурации из переменных окружения"""
    
    # IMAP настройки
    IMAP_SERVER: str = os.getenv('IMAP_SERVER', 'imap.mail.ru')
    IMAP_PORT: int = int(os.getenv('IMAP_PORT', '993'))
    IMAP_LOGIN: str = os.getenv('IMAP_LOGIN', '')
    IMAP_PASSWORD: str = os.getenv('IMAP_PASSWORD', '')
    
    # Настройки поиска письма
    EMAIL_FROM: str = os.getenv('EMAIL_FROM', 'post@mx.forum-auto.ru')
    ATTACHMENT_FILENAME: str = os.getenv('ATTACHMENT_FILENAME', 'FORUM-AUTO_PRICE.zip')
    
    # Пути
    BASE_DIR: Path = Path(os.getenv('BASE_DIR', '/home/rinat/wildberries'))
    DOWNLOAD_DIR: Path = Path(os.getenv('DOWNLOAD_DIR', '/home/rinat/wildberries/tmp'))
    TARGET_DIR: Path = Path(os.getenv('TARGET_DIR', '/home/rinat/wildberries/price'))
    
    @classmethod
    def validate(cls) -> None:
        """Проверяет, что все необходимые переменные окружения установлены"""
        if not cls.IMAP_LOGIN:
            raise ValueError("IMAP_LOGIN не установлен в .env файле")
        if not cls.IMAP_PASSWORD:
            raise ValueError("IMAP_PASSWORD не установлен в .env файле")
        if not cls.EMAIL_FROM:
            raise ValueError("EMAIL_FROM не установлен в .env файле")
        if not cls.ATTACHMENT_FILENAME:
            raise ValueError("ATTACHMENT_FILENAME не установлен в .env файле")


def connect_imap() -> imaplib.IMAP4_SSL:
    """
    Подключается к IMAP серверу
    
    Returns:
        imaplib.IMAP4_SSL: Подключенный IMAP клиент
        
    Raises:
        ValueError: Если настройки не валидны
        Exception: Если не удалось подключиться
    """
    Config.validate()
    
    print(f"Подключение к IMAP серверу {Config.IMAP_SERVER}:{Config.IMAP_PORT}...")
    
    # Создаем SSL контекст
    context = ssl.create_default_context()
    
    try:
        # Подключаемся к серверу
        imap = imaplib.IMAP4_SSL(Config.IMAP_SERVER, Config.IMAP_PORT, ssl_context=context)
        
        # Авторизуемся
        imap.login(Config.IMAP_LOGIN, Config.IMAP_PASSWORD)
        print("Успешное подключение к IMAP серверу")
        
        return imap
    except imaplib.IMAP4.error as e:
        raise Exception(f"Ошибка авторизации IMAP: {e}")
    except Exception as e:
        raise Exception(f"Ошибка подключения к IMAP серверу: {e}")


def decode_filename(filename: Optional[str]) -> Optional[str]:
    """
    Декодирует имя файла из заголовка email
    
    Args:
        filename: Имя файла из заголовка
        
    Returns:
        Декодированное имя файла или None
    """
    if not filename:
        return None
    
    decoded_filename = decode_header(filename)[0]
    if isinstance(decoded_filename[0], bytes):
        return decoded_filename[0].decode(decoded_filename[1] or 'utf-8')
    else:
        return decoded_filename[0]


def find_latest_message_with_attachment(imap: imaplib.IMAP4_SSL) -> Message:
    """
    Находит самое новое письмо от указанного отправителя с нужным вложением
    
    Args:
        imap: Подключенный IMAP клиент
        
    Returns:
        Message: Самое новое письмо с вложением
        
    Raises:
        Exception: Если письмо не найдено
    """
    print(f"Поиск письма от {Config.EMAIL_FROM} с вложением {Config.ATTACHMENT_FILENAME}...")
    
    # Выбираем папку INBOX
    status, _ = imap.select("INBOX")
    if status != 'OK':
        raise Exception("Не удалось выбрать папку INBOX")
    
    # Ищем письма от указанного отправителя
    search_criteria = f'(FROM "{Config.EMAIL_FROM}")'
    status, messages = imap.search(None, search_criteria)
    
    if status != 'OK' or not messages[0]:
        raise Exception(f"Письма от {Config.EMAIL_FROM} не найдены")
    
    # Получаем список ID писем
    email_ids = messages[0].split()
    
    if not email_ids:
        raise Exception(f"Письма от {Config.EMAIL_FROM} не найдены")
    
    print(f"Найдено писем: {len(email_ids)}")
    
    # Оптимизация: сначала получаем только заголовки для сортировки по дате
    # Это экономит память, так как не загружаем полные письма
    print("Получение заголовков писем для сортировки...")
    email_dates: List[Tuple[datetime, bytes]] = []
    
    for email_id in email_ids:
        try:
            # Получаем только заголовок Date, не все письмо
            status, date_data = imap.fetch(email_id, '(BODY[HEADER.FIELDS (DATE)])')
            
            if status != 'OK' or not date_data[0]:
                continue
            
            # Парсим дату из заголовка
            date_header = date_data[0][1].decode('utf-8', errors='ignore')
            if date_header.startswith('Date:'):
                date_str = date_header[5:].strip()
                try:
                    date_obj = parsedate_to_datetime(date_str)
                    email_dates.append((date_obj, email_id))
                except (ValueError, TypeError):
                    # Если не удалось распарсить, используем минимальную дату
                    email_dates.append((datetime.min, email_id))
        except Exception as e:
            # Пропускаем письма с ошибками
            continue
    
    if not email_dates:
        raise Exception(f"Не удалось получить даты писем от {Config.EMAIL_FROM}")
    
    # Сортируем по дате (самое новое первым)
    email_dates.sort(key=lambda x: x[0], reverse=True)
    print(f"Отсортировано писем по дате. Проверяю вложения, начиная с самых новых...")
    
    # Проверяем письма в порядке от новых к старым, останавливаемся при первом найденном
    checked_count = 0
    max_check = min(50, len(email_dates))  # Проверяем максимум 50 самых новых писем
    
    for date_obj, email_id in email_dates[:max_check]:
        checked_count += 1
        if checked_count % 10 == 0:
            print(f"  Проверено {checked_count}/{max_check} писем...")
        
        try:
            # Теперь загружаем полное письмо только для проверки вложения
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Проверяем наличие вложения
            has_attachment = False
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = decode_filename(part.get_filename())
                        
                        if filename == Config.ATTACHMENT_FILENAME:
                            has_attachment = True
                            break
            
            if has_attachment:
                print(f"Найдено письмо с вложением (ID: {email_id.decode()}, дата: {date_obj.strftime('%Y-%m-%d %H:%M:%S')})")
                print(f"Проверено писем: {checked_count}")
                return msg
                
        except Exception as e:
            # Пропускаем письма с ошибками и продолжаем поиск
            continue
    
    raise Exception(f"Письмо с вложением {Config.ATTACHMENT_FILENAME} не найдено среди {checked_count} проверенных писем")


def save_zip_attachment(msg: Message, download_dir: Path) -> Path:
    """
    Сохраняет вложение в указанную папку
    
    Args:
        msg: Email сообщение
        download_dir: Папка для сохранения
        
    Returns:
        Path: Путь к сохраненному файлу
        
    Raises:
        Exception: Если вложение не найдено
    """
    print(f"Скачивание вложения в папку {download_dir}...")
    
    # Создаем папку, если её нет
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Ищем вложение
    if not msg.is_multipart():
        raise Exception("Письмо не содержит вложений")
    
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            filename = decode_filename(part.get_filename())
            
            if filename == Config.ATTACHMENT_FILENAME:
                # Сохраняем файл
                file_path = download_dir / filename
                
                with open(file_path, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                
                print(f"Файл сохранен: {file_path}")
                return file_path
    
    raise Exception(f"Вложение {Config.ATTACHMENT_FILENAME} не найдено в письме")


def unzip_and_get_price_file(zip_path: Path, target_dir: Path) -> Path:
    """
    Распаковывает архив и возвращает путь к прайс-файлу
    
    Args:
        zip_path: Путь к ZIP архиву
        target_dir: Папка для распаковки
        
    Returns:
        Path: Путь к прайс-файлу
        
    Raises:
        Exception: Если архив не найден или прайс-файл не найден
    """
    print(f"Распаковка архива {zip_path} в папку {target_dir}...")
    
    # Создаем папку, если её нет
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Распаковываем архив
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
    except zipfile.BadZipFile:
        raise Exception(f"Файл {zip_path} не является корректным ZIP архивом")
    except Exception as e:
        raise Exception(f"Ошибка при распаковке архива: {e}")
    
    print(f"Архив распакован в {target_dir}")
    
    # Удаляем исходный файл
    print(f"Удаление исходного файла {zip_path}...")
    try:
        zip_path.unlink()
        print("Исходный файл удален")
    except Exception as e:
        print(f"Предупреждение: не удалось удалить исходный файл: {e}")
    
    # Ищем прайс-файл по маске *.csv или *.txt
    # Исключаем уже обработанные файлы с префиксом brand_
    print("Поиск прайс-файла (*.csv или *.txt)...")
    
    csv_files = [f for f in target_dir.glob("*.csv") if not f.name.startswith("brand_")]
    txt_files = [f for f in target_dir.glob("*.txt") if not f.name.startswith("brand_")]
    
    all_files = csv_files + txt_files
    
    if not all_files:
        raise Exception(f"Прайс-файл (*.csv или *.txt) не найден в {target_dir}")
    
    # Сортируем по времени модификации (самый новый первым) и берем первый
    all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    price_file = all_files[0]
    print(f"Найден прайс-файл: {price_file}")
    
    return price_file


def cleanup_old_brand_files(target_dir: Path) -> None:
    """
    Удаляет старые файлы брендов (brand_*.csv) перед обработкой нового файла
    
    Args:
        target_dir: Папка с файлами брендов
    """
    brand_files = list(target_dir.glob("brand_*.csv"))
    if brand_files:
        for brand_file in brand_files:
            try:
                brand_file.unlink()
            except Exception as e:
                print(f"Предупреждение: не удалось удалить {brand_file}: {e}")


def sanitize_filename(brand: str) -> str:
    """
    Заменяет запрещенные символы в имени файла на _
    
    Args:
        brand: Название бренда
        
    Returns:
        str: Очищенное имя файла
    """
    # Запрещенные символы: / \ : * ? " < > |
    forbidden_chars = r'[/\\:*?"<>|]'
    return re.sub(forbidden_chars, '_', brand)


def detect_encoding(price_path: Path) -> str:
    """
    Определяет кодировку файла
    
    Args:
        price_path: Путь к файлу
        
    Returns:
        str: Кодировка файла (utf-8 или cp1251)
    """
    # Пробуем сначала utf-8
    try:
        with open(price_path, 'r', encoding='utf-8') as f:
            # Читаем первые строки для проверки
            for i, _ in enumerate(f):
                if i >= 10:
                    break
        encoding = 'utf-8'
    except UnicodeDecodeError:
        # Если не получилось, пробуем cp1251
        encoding = 'cp1251'
        try:
            with open(price_path, 'r', encoding='cp1251') as f:
                for i, _ in enumerate(f):
                    if i >= 10:
                        break
        except UnicodeDecodeError:
            raise Exception(f"Не удалось определить кодировку файла {price_path}")
    
    return encoding


def detect_delimiter(sample: str) -> csv.Dialect:
    """
    Определяет разделитель CSV файла
    
    Args:
        sample: Образец текста из файла
        
    Returns:
        csv.Dialect: Диалект CSV с определенным разделителем
    """
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(sample, delimiters=',;\t')
    # Настраиваем параметры для корректной обработки кавычек
    dialect.doublequote = True
    dialect.quoting = csv.QUOTE_MINIMAL
    dialect.escapechar = None
    return dialect


def split_price_by_brand(price_path: Path, output_dir: Path) -> None:
    """
    Разбивает прайс-файл по брендам (первая колонка)
    Оптимизировано для работы с большими файлами - записывает построчно, не загружая все в память
    
    Args:
        price_path: Путь к прайс-файлу
        output_dir: Папка для сохранения файлов по брендам
        
    Raises:
        Exception: Если файл не может быть прочитан
    """
    print(f"Разбиение прайс-файла {price_path} по брендам...")
    
    # Определяем кодировку
    encoding = detect_encoding(price_path)
    
    # Читаем первые строки для определения разделителя
    sample_lines: List[str] = []
    with open(price_path, 'r', encoding=encoding) as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            sample_lines.append(line)
    sample = ''.join(sample_lines)
    
    # Определяем разделитель
    dialect = detect_delimiter(sample)
    
    # Словарь для отслеживания открытых файлов и писателей для каждого бренда
    brand_writers: Dict[str, Any] = {}
    brand_files: Dict[str, Path] = {}
    header: Optional[List[str]] = None
    row_count = 0
    processed_brands: set = set()
    
    try:
        with open(price_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f, dialect=dialect)
            
            for row_num, row in enumerate(reader):
                if not row:
                    continue
                
                # Первая строка - заголовок
                if row_num == 0:
                    header = row
                    continue
                
                # Первая колонка - бренд
                if len(row) == 0:
                    continue
                
                brand = row[0].strip()
                
                if not brand:
                    continue
                
                # Нормализуем название бренда: убираем только лишние пробелы (но сохраняем регистр)
                # Это поможет группировать "JapanParts" и "JapanParts " как один бренд
                brand_key = ' '.join(brand.split())
                
                # Создаем файл и писатель для бренда, если его еще нет
                if brand_key not in brand_writers:
                    # Используем оригинальное название для имени файла
                    sanitized_brand = sanitize_filename(brand)
                    brand_file_path = output_dir / f"brand_{sanitized_brand}.csv"
                    brand_files[brand_key] = brand_file_path
                    
                    # Открываем файл для записи
                    out_f = open(brand_file_path, 'w', encoding=encoding, newline='')
                    writer = csv.writer(
                        out_f,
                        delimiter=dialect.delimiter,
                        quotechar=dialect.quotechar,
                        doublequote=True,
                        quoting=csv.QUOTE_ALL,
                        escapechar=None
                    )
                    
                    # Записываем заголовок сразу
                    writer.writerow(header)
                    
                    brand_writers[brand_key] = {
                        'file': out_f,
                        'writer': writer
                    }
                    processed_brands.add(brand_key)
                
                # Записываем строку сразу в файл бренда (не накапливаем в памяти)
                brand_writers[brand_key]['writer'].writerow(row)
                row_count += 1
                
                # Показываем прогресс каждые 100000 строк
                if row_count % 100000 == 0:
                    print(f"  Обработано строк: {row_count}, брендов: {len(processed_brands)}")
    
    finally:
        # Закрываем все открытые файлы
        for brand_key, writer_data in brand_writers.items():
            try:
                writer_data['file'].close()
            except Exception as e:
                print(f"  Предупреждение: ошибка при закрытии файла для бренда {brand_key}: {e}")
    
    if not header:
        raise Exception("Файл не содержит заголовка")
    
    print(f"Обработано строк: {row_count}")
    print(f"Создано файлов по брендам: {len(brand_files)}")


def main() -> None:
    """Основная функция"""
    imap: Optional[imaplib.IMAP4_SSL] = None
    try:
        # Валидируем конфигурацию
        Config.validate()
        
        # Подключаемся к IMAP
        imap = connect_imap()
        
        # Находим письмо с вложением
        msg = find_latest_message_with_attachment(imap)
        
        # Скачиваем вложение
        zip_path = save_zip_attachment(msg, Config.DOWNLOAD_DIR)
        
        # Распаковываем и получаем путь к прайс-файлу
        price_file = unzip_and_get_price_file(zip_path, Config.TARGET_DIR)
        
        # Очищаем старые файлы брендов перед обработкой нового файла
        cleanup_old_brand_files(Config.TARGET_DIR)
        
        # Разбиваем прайс по брендам
        split_price_by_brand(price_file, Config.TARGET_DIR)
        
        print("\nОперация завершена успешно!")
        
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        print("Проверьте файл .env и убедитесь, что все необходимые переменные установлены")
        raise
    except Exception as e:
        print(f"Ошибка: {e}")
        raise
    finally:
        # Закрываем соединение
        if imap:
            try:
                imap.close()
                imap.logout()
                print("Соединение с IMAP сервером закрыто")
            except Exception:
                pass


if __name__ == "__main__":
    main()
