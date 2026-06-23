import os
import struct
from datetime import datetime

def decode_fat_datetime(fat_date, fat_time=0):
    """Декодирует дату и время из формата DOS/FAT в объект datetime Python"""
    if fat_date == 0:
        return None
    # Разбор даты: Биты 0-4: День, 5-8: Месяц, 9-15: Год (от 1980)
    day = fat_date & 0x1F
    month = (fat_date >> 5) & 0x0F
    year = ((fat_date >> 9) & 0x7F) + 1980
    
    # Разбор времени: Биты 0-4: Двухсекундные интервалы, 5-10: Минуты, 11-15: Часы
    second = (fat_time & 0x1F) * 2
    minute = (fat_time >> 5) & 0x3F
    hour = (fat_time >> 11) & 0x1F
    
    # Защита от некорректных значений в дампе прошивки
    try:
        return datetime(year, month, day, hour, minute, min(second, 59))
    except ValueError:
        return None

def unpack_firmware(firmware_path, output_dir="upgrade"):
    if not os.path.exists(firmware_path):
        print(f"[-] Ошибка: Файл прошивки '{firmware_path}' не найден!")
        return

    # Создаем папку и открываем манифест
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "manifest.txt")
    manifest = open(manifest_path, "w", encoding="utf-8")

    def log_message(message):
        """Функция одновременного вывода в терминал и файл манифеста"""
        print(message)
        manifest.write(message + "\n")

    # Константы геометрии Flat FAT32
    fat_start = 0x4010
    cluster_size = 4096
    cluster_2_phys_offset = 0x203010  # Начало Кластера 2 на диске

    log_message(f"[*] Начало распаковки прошивки: {firmware_path}")
    log_message("-" * 60)

    with open(firmware_path, "rb") as f:
        # --- ШАГ 1: Чтение цепочки каталогов в FAT ---
        directory_clusters = [2]  # Корневой каталог всегда начинается с Кластера 2
        current_cluster = 2
        
        while True:
            f.seek(fat_start + (current_cluster * 4))
            next_cluster_bytes = f.read(4)
            if len(next_cluster_bytes) < 4:
                break
            next_cluster = struct.unpack("<I", next_cluster_bytes)[0] & 0x0FFFFFFF
            
            if 0x00000002 <= next_cluster < 0x0FFFFFF8:
                directory_clusters.append(next_cluster)
                current_cluster = next_cluster
            else:
                break

        log_message(f"[+] Найдена цепочка кластеров таблицы файлов: {[hex(c) for c in directory_clusters]}")
        log_message("-" * 60)

        # --- ШАГ 2: Обход каталогов и парсинг файлов ---
        lfn_buffer = {}  # Буфер для сборки длинного имени по ID последовательности

        for dir_cluster in directory_clusters:
            cluster_offset = cluster_2_phys_offset + ((dir_cluster - 2) * cluster_size)
            f.seek(cluster_offset)
            cluster_data = f.read(cluster_size)

            for i in range(0, cluster_size, 32):
                record = cluster_data[i:i+32]
                if len(record) < 32 or record[0] == 0x00: 
                    continue # Пустая запись или конец каталога
                
                attr = record[0x0B]

                # Проверяем, является ли запись частью Длинного Имени (LFN)
                if attr == 0x0F:
                    sequence_id = record[0]
                    if sequence_id == 0xE5: 
                        continue # Удаленная LFN-запись
                    
                    # Собираем символы UTF-16LE из LFN-структуры
                    name_part1 = record[1:11]
                    name_part2 = record[14:26]
                    name_part3 = record[28:32]
                    raw_chars = name_part1 + name_part2 + name_part3
                    
                    try:
                        # Декодируем и очищаем от концевых FF/00
                        chars = raw_chars.decode('utf-16le').split('\x00')[0]
                    except:
                        chars = ""
                    
                    pure_id = sequence_id & 0x3F
                    lfn_buffer[pure_id] = chars
                    continue

                # Если это стандартная DOS-запись (файл или удаленный файл)
                is_deleted = record[0] == 0xE5
                
                # Собираем длинное имя из буфера
                if lfn_buffer:
                    sorted_parts = [lfn_buffer[k] for k in sorted(lfn_buffer.keys()) if k in lfn_buffer]
                    long_name = "".join(sorted_parts).strip()
                    lfn_buffer.clear() # Очищаем буфер
                    
                    # Жесткая очистка имени от артефактов FAT (убираем хвосты типа ~0, нули и мусор)
                    if "~" in long_name:
                        # Отрезаем всё после тильды, если она прилепилась к концу расширения
                        base_part = long_name.split("~")[0]
                        # Восстанавливаем правильное расширение по сигнатуре DOS-записи, если обрезали лишнее
                        ext_dos = record[8:11].decode('ascii', errors='ignore').strip().lower()
                        if not base_part.lower().endswith(ext_dos):
                            # Если расширение пострадало, склеиваем имя заново корректно
                            name_part = os.path.splitext(base_part)[0]
                            long_name = f"{name_part}.{ext_dos}"
                        else:
                            long_name = base_part
                else:
                    name_83 = record[0:8].decode('ascii', errors='ignore').strip()
                    ext_83 = record[8:11].decode('ascii', errors='ignore').strip()
                    long_name = f"{name_83}.{ext_83}".lower()

                # Дополнительная финальная очистка от непечатных символов
                long_name = "".join([c for c in long_name if c.isalnum() or c in "._-❌"]).strip()
                if not long_name:
                    continue

                if is_deleted:
                    long_name = "❌_" + long_name

                # --- ЧИТАЕМ ДАННЫЕ ВРЕМЕНИ ИЗ DOS-ЗАПИСИ ---
                # Вытаскиваем raw-байты по вашей структуре
                raw_c_time = struct.unpack("<H", record[0x0E:0x10])[0]
                raw_c_date = struct.unpack("<H", record[0x10:0x12])[0]
                raw_a_date = struct.unpack("<H", record[0x12:0x14])[0]
                raw_m_time = struct.unpack("<H", record[0x16:0x18])[0]
                raw_m_date = struct.unpack("<H", record[0x18:0x1A])[0]

                # Декодируем в объекты datetime
                dt_create = decode_fat_datetime(raw_c_date, raw_c_time)
                dt_access = decode_fat_datetime(raw_a_date, 0)
                dt_modify = decode_fat_datetime(raw_m_date, raw_m_time)

                # Читаем начальный кластер и размер из DOS-записи
                start_cluster_high = struct.unpack("<H", record[0x14:0x16])[0]
                start_cluster_low = struct.unpack("<H", record[0x1A:0x1C])[0]
                start_cluster = (start_cluster_high << 16) | start_cluster_low
                file_size = struct.unpack("<I", record[0x1C:0x20])[0]

                if start_cluster < 2 or file_size == 0:
                    continue

                # --- ШАГ 3: Извлечение и обработка файла ---
                file_phys_offset = cluster_2_phys_offset + ((start_cluster - 2) * cluster_size)
                
                saved_pos = f.tell()
                f.seek(file_phys_offset)
                payload = bytearray(f.read(file_size))
                
                # Получаем чистое имя для анализа расширения (без значка удаления)
                check_name = long_name.replace("❌_", "").lower()
                
                # Проверяем, начинается ли блок с кастомного маркера Actions
                has_marker = payload[:16] == b"\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff\x75"

                if has_marker:
                    # Если есть маркер 11 22... — сохраняем КАК ЕСТЬ, ничего не меняем
                    pass
                else:
                    # Маска XOR 0x38 для ДЛЯ ВСЕХ ОСТАЛЬНЫХ ФАЙЛОВ
                    payload = bytearray([b ^ 0x38 for b in payload])

                """
                elif check_name.endswith(".xml"):
                    # Маска XOR 0x38 для XML
                    payload = bytearray([b ^ 0x38 for b in payload])
                elif check_name.endswith(".ini"):
                    # Маска XOR 0x38 для INI
                    payload = bytearray([b ^ 0x38 for b in payload])
                elif check_name.endswith(".bin"):
                    # Маска XOR 0x38 для BIN
                    payload = bytearray([b ^ 0x38 for b in payload])
                elif check_name.endswith(".fw"):
                    # Маска XOR 0x38 для FW
                    payload = bytearray([b ^ 0x38 for b in payload])
                """

                # Записываем чистый файл в папку upgrade
                safe_name = long_name.replace("❌_", "DELETED_")
                output_path = os.path.join(output_dir, safe_name)
                with open(output_path, "wb") as out_file:
                    out_file.write(payload)

                # --- ПРОПИСЫВАЕМ ВРЕМЯ В ФАЙЛ НА ДИСКЕ ---
                if dt_modify and dt_access:
                    # os.utime принимает timestamp (секунды Эпохи) для (atime, mtime)
                    timestamp_a = dt_access.timestamp()
                    timestamp_m = dt_modify.timestamp()
                    os.utime(output_path, (timestamp_a, timestamp_m))

                # Строим красивые строки дат для лога
                str_c = dt_create.strftime('%Y-%m-%d %H:%M:%S') if dt_create else "Н/Д"
                str_m = dt_modify.strftime('%Y-%m-%d %H:%M:%S') if dt_modify else "Н/Д"
                str_a = dt_access.strftime('%Y-%m-%d') if dt_access else "Н/Д"

                # Определяем правильный префикс для лога в зависимости от статуса файла
                prefix = "[УДАЛ]" if is_deleted else "[ФАЙЛ]"

                # Выводим расширенные логи в терминал и манифест
                log_message(f"{prefix} {long_name} | Кластер: {hex(start_cluster)} | Размер: {file_size} байт")
                log_message(f"       Создан: {str_c} | Изменен: {str_m} | Доступ: {str_a}")

                f.seek(saved_pos)

        log_message("-" * 60)

        # --- ШАГ 4: Извлечение финального скрытого блока по адресу из 0x0C ---
        f.seek(0x0C)
        block_pointer_bytes = f.read(4)
        if len(block_pointer_bytes) == 4:
            block_pointer = struct.unpack("<I", block_pointer_bytes)[0]
            
            final_block_phys_offset = block_pointer + 16
            
            f.seek(final_block_phys_offset + 16)
            final_size_bytes = f.read(4)
            if len(final_size_bytes) == 4:
                final_size = struct.unpack("<I", final_size_bytes)[0]
                
                f.seek(final_block_phys_offset)
                final_payload = f.read(final_size + 32)
                
                main_bin_path = os.path.join(output_dir, "main.bin")
                with open(main_bin_path, "wb") as out_main:
                    out_main.write(final_payload)
                    
                log_message(f"[БЛОК] main.bin | Смещение (из 0x0C + 16): {hex(final_block_phys_offset)} | Размер: {len(final_payload)} байт")
            else:
                log_message("[-] Не удалось прочитать размер финального блока.")
        else:
            log_message("[-] Не удалось прочитать указатель из смещения 0x0C.")

    log_message("-" * 60)
    log_message("[+++] Распаковка полностью завершена!")
    manifest.close()

# Запуск unpacker-а. Подставьте имя вашего файла прошивки.
unpack_firmware("upgrade.fw")
