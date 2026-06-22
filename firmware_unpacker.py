print("================================================")
print("Распаковщик прошивок для Смарт часов на ATS3085S")
print("================================================")

import os
import sys
import struct
import string
import re

def is_valid_name_struct(name_bytes):
    """ Проверка, что байты содержат допустимые символы для имен файлов """
    allowed_chars = set(string.ascii_letters + string.digits + "._-$~#%&{}()@!^'` ")
    for b in name_bytes:
        if b == 0x00:
            continue
        if chr(b) not in allowed_chars:
            return False
    return True

def clean_string(byte_data):
    """ Корректно декодирует строку, отсекая всё после первого нулевого байта """
    try:
        # Находим позицию первого нулевого байта
        null_pos = byte_data.find(b'\x00')
        if null_pos != -1:
            byte_data = byte_data[:null_pos]
        text = byte_data.decode('ascii', errors='ignore').strip()
        return text
    except:
        return ""

def format_manifest_line(prefix_and_name, offset_hex, size_hex):
    """ Выравнивает колонку смещения строго с 24-го символа """
    part_name = prefix_and_name.ljust(24)
    part_offset = offset_hex.ljust(12)
    return f"{part_name}{part_offset}{size_hex}\n"

def unpack_full_firmware(fw_path):
    if not os.path.exists(fw_path):
        print(f"[-] Ошибка: Файл '{fw_path}' не найден!")
        return

    # Создаем папку верхнего уровня по имени прошивки без расширения .fw
    base_name, _ = os.path.splitext(os.path.basename(fw_path))
    main_output_dir = os.path.abspath(base_name)
    os.makedirs(main_output_dir, exist_ok=True)
    
    print(f"[*] Создана главная папка: {main_output_dir}")
    
    with open(fw_path, 'rb') as f:
        fw_data = f.read()

    # Открываем файл манифеста на запись
    manifest_path = os.path.join(main_output_dir, "manifest.txt")
    manifest_file = open(manifest_path, 'w', encoding='utf-8')
    
    MASTER_TABLE_START = 0x20
    ENTRY_SIZE = 32

    print("[*] Шаг 1: Сканирование главного манифеста...")
    offset = MASTER_TABLE_START
    
    while True:
        entry = fw_data[offset : offset + ENTRY_SIZE]
        if len(entry) < ENTRY_SIZE or entry == b'\x00' * ENTRY_SIZE:
            break
            
        try:
            filename = clean_string(entry[0:16])
            
            # Если имя не прочиталось, пропускаем запись
            if not filename:
                offset += ENTRY_SIZE
                continue
                
            file_offset = struct.unpack('<I', entry[16:20])[0]
            file_size = struct.unpack('<I', entry[20:24])[0]
            
            if file_size == 0 or file_offset == 0 or file_offset + file_size > len(fw_data):
                offset += ENTRY_SIZE
                continue
                
            # Заносим главный файл в manifest.txt с идеальным выравниванием
            manifest_file.write(format_manifest_line(filename, hex(file_offset), hex(file_size)))
            print(f"[+] Файл: {filename:24} | Смещение: {hex(file_offset):<10} | Размер: {file_size} байт")
            
            # Извлекаем данные главного файла и сохраняем на диск
            file_payload = fw_data[file_offset : file_offset + file_size]
            main_file_path = os.path.join(main_output_dir, filename)
            with open(main_file_path, 'wb') as mf:
                mf.write(file_payload)
                
            # Проверяем, является ли файл контейнером
            is_sdfs = False
            is_attt = False
            container_file_count = 0
            
            if file_size >= 32 and is_valid_name_struct(file_payload[0:12]):
                container_file_count = struct.unpack('<I', file_payload[12:16])[0]
                
                if 0 < container_file_count < 1000:
                    # Проверяем имя по маске sdfs_*.bin (независимо от регистра)
                    if re.match(r'^sdfs_.\.bin$', filename.lower()):
                        is_sdfs = True
                    else:
                        is_attt = True

            # Распаковка контейнеров в соответствии с их типом
            if is_sdfs or is_attt:
                folder_name, _ = os.path.splitext(filename)
                sub_output_dir = os.path.join(main_output_dir, folder_name)
                os.makedirs(sub_output_dir, exist_ok=True)
                
                mode_str = "SDFS" if is_sdfs else "ATTT_BIN"
                print(f"    [{mode_str}] Обнаружен контейнер! Распаковка в папку '{folder_name}'...")
                
                sub_offset = 0x20
                for _ in range(container_file_count):
                    sub_entry = file_payload[sub_offset : sub_offset + 32]
                    if len(sub_entry) < 32:
                        break
                        
                    if is_sdfs:
                        inner_name = clean_string(sub_entry[0:12])
                        inner_offset = struct.unpack('<I', sub_entry[12:16])[0]
                        inner_size = struct.unpack('<I', sub_entry[16:20])[0]
                    else:
                        inner_name = clean_string(sub_entry[0:12])
                        inner_offset = struct.unpack('<I', sub_entry[16:20])[0]
                        inner_size = struct.unpack('<I', sub_entry[20:24])[0]
                        
                    if not inner_name:
                        sub_offset += 32
                        continue
                        
                    # Математика абсолютных координат относительно начала всего прошивочного .fw
                    absolute_offset = file_offset + inner_offset
                    
                    # Логируем в manifest.txt со стрелочкой и новым сквозным выравниванием колонок
                    prefix_name = f"  \\-- {inner_name}"
                    manifest_file.write(format_manifest_line(prefix_name, hex(absolute_offset), hex(inner_size)))
                    
                    # Извлекаем и сохраняем подфайл во вложенную папку
                    inner_payload = file_payload[inner_offset : inner_offset + inner_size]
                    inner_file_path = os.path.join(sub_output_dir, inner_name)
                    with open(inner_file_path, 'wb') as inf:
                        inf.write(inner_payload)
                        
                    sub_offset += 32
                    
        except Exception as e:
            print(f"[-] Ошибка при обработке записи на смещении {hex(offset)}: {e}")
            
        offset += ENTRY_SIZE

    manifest_file.close()
    print(f"\n[!] Распаковка успешно завершена. Все файлы извлечены, manifest.txt отформатирован.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[*] Использование: python firmware_unpacker.py <имя_файла_прошивки.fw>")
        print("    Пример: python firmware_unpacker.py A5S16GLY_C229G_D2-2026-02-03-17-32_V1_72_86_debug.fw")
    else:
        target_firmware = sys.argv[1]
        unpack_full_firmware(target_firmware)