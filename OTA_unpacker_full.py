import os
import sys
import struct
import string
import re
import lzma

# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ 
# =====================================================================

def is_valid_name_struct(name_bytes):
    """ Проверка, что байты содержат допустимые символы для имен файлов """
    allowed_chars = set(string.ascii_letters + string.digits + "._-$~#%&{}()@!^'` ")
    for b in name_bytes:
        if b == 0x00:
            continue
        if chr(b) not in allowed_chars:
            return False
    return True

def clean_string_s1(byte_data):
    """ Корректно декодирует строку, отсекая всё после первого нулевого байта (Алгоритм Скрипта 1) """
    try:
        null_pos = byte_data.find(b'\x00')
        if null_pos != -1:
            byte_data = byte_data[:null_pos]
        text = byte_data.decode('ascii', errors='ignore').strip()
        return text
    except:
        return ""

def clean_string_s2(byte_array):
    """ Очищает байтовую строку от нулевых байт и декодирует в текст (Алгоритм Скрипта 2) """
    try:
        clean_bytes = byte_array.split(b'\x00')[0]
        return clean_bytes.decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

def format_manifest_line_s1(prefix_and_name, offset_hex, size_hex):
    """ Выравнивает колонку смещения строго с 24-го символа """
    part_name = prefix_and_name.ljust(24)
    part_offset = offset_hex.ljust(12)
    return f"{part_name}{part_offset}{size_hex}\n"

def format_manifest_line_s2(filename, offset_hex, size_hex):
    """ Форматирует строку для записи в manifest.txt Скрипта 2 """
    return f"{filename:<30} | Смещение: {offset_hex:<10} | Размер: {size_hex}\n"

def decompress_full_stream(payload):
    """ Полная декомпрессия склеенных XZ блоков из сжатого контейнера """
    if len(payload) < 16:
        return payload
        
    buffer = payload[16:]
    decompressed_data = b""
    
    while buffer:
        if b"\xfd7zXZ\x00" not in buffer[:40]:
            pos = buffer.find(b"\xfd7zXZ\x00")
            if pos == -1:
                break
            buffer = buffer[pos:]
            
        try:
            decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
            decompressed_block = decompressor.decompress(buffer)
            decompressed_data += decompressed_block
            
            remaining_data = decompressor.unused_data
            if not remaining_data:
                break
            buffer = remaining_data[16:]
        except lzma.LZMAError:
            break
            
    return decompressed_data if decompressed_data else payload


# =====================================================================
# ЛОГИКА РАСПАКОВКИ ИЗ ПАМЯТИ
# =====================================================================

def unpack_full_firmware_from_memory(fw_data, target_dir):
    """ Принимает распакованный массив байт прошивки Скрипта 2 и извлекает из него файлы """
    main_output_dir = os.path.abspath(target_dir)
    os.makedirs(main_output_dir, exist_ok=True)
    
    manifest_path = os.path.join(main_output_dir, "manifest.txt")
    manifest_file = open(manifest_path, 'w', encoding='utf-8')
    
    MASTER_TABLE_START = 0x200
    ENTRY_SIZE = 32

    print("    [*] Сканирование главного манифеста внутри TEMP.bin...")
    offset = MASTER_TABLE_START
    
    while True:
        entry = fw_data[offset : offset + ENTRY_SIZE]
        if len(entry) < ENTRY_SIZE or entry == b'\x00' * ENTRY_SIZE:
            break
            
        try:
            filename = clean_string_s2(entry[0:16])
            if not filename:
                offset += ENTRY_SIZE
                continue
                
            file_offset = struct.unpack('<I', entry[16:20])[0]
            file_size = struct.unpack('<I', entry[20:24])[0]
            
            if file_size == 0 or file_offset == 0 or file_offset + file_size > len(fw_data):
                offset += ENTRY_SIZE
                continue
                
            manifest_file.write(format_manifest_line_s2(filename, hex(file_offset), hex(file_size)))
            print(f"    [+] Файл: {filename:24} | Смещение: {hex(file_offset):<10} | Размер: {file_size} байт")
            
            file_payload = fw_data[file_offset : file_offset + file_size]
            main_file_path = os.path.join(main_output_dir, filename)
            with open(main_file_path, 'wb') as mf:
                mf.write(file_payload)
                
            is_sdfs = False
            container_file_count = 0
            working_payload = file_payload

            if len(working_payload) >= 32 and is_valid_name_struct(working_payload[0:12]):
                container_file_count = struct.unpack('<I', working_payload[12:16])[0]
                if 0 < container_file_count < 1000 and "sdfs" in filename.lower():
                    is_sdfs = True

            if is_sdfs:
                folder_name, _ = os.path.splitext(filename)
                sub_output_dir = os.path.join(main_output_dir, f"{folder_name}_extracted")
                os.makedirs(sub_output_dir, exist_ok=True)
                print(f"        [SDFS] Обнаружен контейнер! Распаковка в папку '{folder_name}_extracted'...")
                
                sub_offset = 0x20
                for _ in range(container_file_count):
                    sub_entry = working_payload[sub_offset : sub_offset + 32]
                    if len(sub_entry) < 32:
                        break
                        
                    inner_name = clean_string_s2(sub_entry[0:12])
                    inner_offset = struct.unpack('<I', sub_entry[12:16])[0]
                    inner_size = struct.unpack('<I', sub_entry[16:20])[0]
                        
                    if not inner_name:
                        sub_offset += 32
                        continue
                        
                    absolute_offset = file_offset + inner_offset
                    prefix_name = f"  \\-- {inner_name}"
                    manifest_file.write(format_manifest_line_s2(prefix_name, hex(absolute_offset), hex(inner_size)))
                    print(f"            -> Извлечен файл: {inner_name} | Размер: {inner_size} байт")
                    
                    inner_payload = working_payload[inner_offset : inner_offset + inner_size]
                    inner_file_path = os.path.join(sub_output_dir, inner_name)
                    with open(inner_file_path, 'wb') as inf:
                        inf.write(inner_payload)
                        
                    sub_offset += 32
                    
        except Exception as e:
            print(f"    [-] Ошибка при обработке записи Скрипта 2 на смещении {hex(offset)}: {e}")
            
        offset += ENTRY_SIZE

    manifest_file.close()
    print(f"    [!] Распаковка TEMP.bin завершена. Manifest.txt обновлен.")


# =====================================================================
# АВТОМАТИЧЕСКИЙ ТРИГГЕР ЗАПУСКА СКРИПТА ДЛЯ TEMP.bin
# =====================================================================

def trigger_script2_process(temp_bin_path):
    """ Вызывается автоматически Скриптом 1 сразу после записи TEMP.bin на диск """
    base_dir = os.path.dirname(temp_bin_path)
    output_dir = os.path.join(base_dir, "TEMP")
    first_block_file = os.path.join(output_dir, "main.bin")
    
    os.makedirs(output_dir, exist_ok=True)

    try:
        print(f"    [*] Открытие файла TEMP.bin...")
        with open(temp_bin_path, "rb") as f:
            f.seek(0x18)
            block1_len = struct.unpack("<I", f.read(4))[0]
            
            f.seek(0x24)
            block1_offset = struct.unpack("<I", f.read(4))[0]
            
            f.seek(block1_offset)
            block1_data = f.read(block1_len)
            
            with open(first_block_file, "wb") as out_f:
                out_f.write(block1_data)
            print(f"    [+] Первый блок сохранен в TEMP как main.bin (Смещение: 0x{block1_offset:X}, Размер: {block1_len} байт)")

            f.seek(block1_offset + block1_len)
            buffer = f.read()

        block_idx = 0
        all_decompressed_data = b""

        print(f"    [*] Размер сжатых данных: {len(buffer)} байт. Запуск конвейера LZMA...")

        while buffer:
            if b"\xfd7zXZ\x00" not in buffer[:0x110]:
                pos = buffer.find(b"\xfd7zXZ\x00")
                if pos == -1:
                    print("[*] Оставшиеся данные не содержат XZ блоков. Завершаем декомпрессию.")
                    break
                buffer = buffer[pos:]

            block_idx += 1
            try:
                decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
                decompressed_block = decompressor.decompress(buffer)
                
                all_decompressed_data += decompressed_block
                print(f"     -> Блок #{block_idx}: Распакован. +{len(decompressed_block)} байт.")
                
                remaining_data = decompressor.unused_data
                if not remaining_data:
                    break
                    
                buffer = remaining_data[16:]
                
            except lzma.LZMAError as e:
                print(f"[-] Ошибка LZMA на блоке #{block_idx}: {e}")
                break

        if all_decompressed_data:
            print(f"\n    [*] Передаем массив данных ({len(all_decompressed_data)} байт) парсеру файловой системы...")
            unpack_full_firmware_from_memory(all_decompressed_data, output_dir)
        else:
            print("[-] Критическая ошибка: Не удалось распаковать массив LZMA-данных. Парсинг отменен.")
            
    except Exception as e:
        print(f"[-] Критическая ошибка выполнения Скрипта 2: {e}")

# =====================================================================
# ОСНОВНОЙ ПРОЦЕСС РАСПАКОВКИ
# =====================================================================

def unpack_full_firmware(fw_path):
    if not os.path.exists(fw_path):
        print(f"[-] Ошибка: Файл '{fw_path}' не найден!")
        return

    base_name, _ = os.path.splitext(os.path.basename(fw_path))
    main_output_dir = os.path.abspath(base_name)
    os.makedirs(main_output_dir, exist_ok=True)
    
    with open(fw_path, 'rb') as f:
        fw_data = f.read()

    manifest_path = os.path.join(main_output_dir, "manifest.txt")
    manifest_file = open(manifest_path, 'w', encoding='utf-8')
    
    MASTER_TABLE_START = 0x200
    ENTRY_SIZE = 32

    print("[*] Шаг 1: Сканирование главного манифеста...")
    offset = MASTER_TABLE_START
    
    while True:
        entry = fw_data[offset : offset + ENTRY_SIZE]
        if len(entry) < ENTRY_SIZE or entry == b'\x00' * ENTRY_SIZE:
            break
            
        try:
            filename = clean_string_s1(entry[0:16])
            if not filename:
                offset += ENTRY_SIZE
                continue
                
            file_offset = struct.unpack('<I', entry[16:20])[0]
            file_size = struct.unpack('<I', entry[20:24])[0]
            
            if file_size == 0 or file_offset == 0 or file_offset + file_size > len(fw_data):
                offset += ENTRY_SIZE
                continue
                
            manifest_file.write(format_manifest_line_s1(filename, hex(file_offset), hex(file_size)))
            print(f"[+] Файл: {filename:24} | Смещение: {hex(file_offset):<10} | Размер: {file_size} байт")
            
            file_payload = fw_data[file_offset : file_offset + file_size]
            main_file_path = os.path.join(main_output_dir, filename)
            if file_payload.startswith(b"LZMA"):
                print(f"    [LZMA] Распаковка файла {filename}...")
                working_payload = decompress_full_stream(file_payload)
                with open(main_file_path, 'wb') as mf:
                    mf.write(working_payload)
                if filename.lower() == "temp.bin":
                    print(f"    [*] Передаем массив данных ({len(working_payload)} байт) парсеру файловой системы...")
                    base_dir = os.path.dirname(main_file_path)
                    output_dir = os.path.join(base_dir, "TEMP")
                    os.makedirs(output_dir, exist_ok=True)
                    unpack_full_firmware_from_memory(working_payload, output_dir)
            else:
                working_payload = file_payload
                with open(main_file_path, 'wb') as mf:
                    mf.write(working_payload)
                if filename.lower() == "temp.bin":
                    trigger_script2_process(main_file_path)
                
            is_sdfs = False
            is_attt = False
            container_file_count = 0
            
            is_sdfs_name = bool(re.match(r'^sdfs_.\.bin$', filename.lower()))
            
            if len(working_payload) >= 32 and is_valid_name_struct(working_payload[0:12]):
                container_file_count = struct.unpack('<I', working_payload[12:16])[0]
                
                if 0 < container_file_count < 1000:
                    if is_sdfs_name:
                        is_sdfs = True
                    else:
                        is_attt = True

            if is_sdfs or is_attt:
                folder_name, _ = os.path.splitext(filename)
                sub_output_dir = os.path.join(main_output_dir, f"{folder_name}_extracted")
                os.makedirs(sub_output_dir, exist_ok=True)
                
                mode_str = "SDFS" if is_sdfs else "ATTT_BIN"
                print(f"    [{mode_str}] Обнаружен контейнер! Распаковка в папку '{folder_name}_extracted'...")
                
                sub_offset = 0x20
                for _ in range(container_file_count):
                    sub_entry = working_payload[sub_offset : sub_offset + 32]
                    if len(sub_entry) < 32:
                        break
                        
                    if is_sdfs:
                        inner_name = clean_string_s1(sub_entry[0:12])
                        inner_offset = struct.unpack('<I', sub_entry[12:16])[0]
                        inner_size = struct.unpack('<I', sub_entry[16:20])[0]
                    else:
                        inner_name = clean_string_s1(sub_entry[0:12])
                        inner_offset = struct.unpack('<I', sub_entry[16:20])[0]
                        inner_size = struct.unpack('<I', sub_entry[20:24])[0]
                        
                    if not inner_name:
                        sub_offset += 32
                        continue
                        
                    absolute_offset = file_offset + inner_offset
                    
                    prefix_name = f"  \\-- {inner_name}"
                    manifest_file.write(format_manifest_line_s1(prefix_name, hex(absolute_offset), hex(inner_size)))
                    print(f"        -> Извлечен файл: {inner_name} | Размер: {inner_size} байт")
                    
                    inner_payload = working_payload[inner_offset : inner_offset + inner_size]
                    inner_file_path = os.path.join(sub_output_dir, inner_name)
                    with open(inner_file_path, 'wb') as inf:
                        inf.write(inner_payload)
                        
                    #if inner_name.lower() == "temp.bin":
                    #    trigger_script2_process(inner_file_path)
                        
                    sub_offset += 32
                    
        except Exception as e:
            print(f"[-] Ошибка при обработке записи на смещении {hex(offset)}: {e}")
            
        offset += ENTRY_SIZE

    manifest_file.close()
    print(f"\n[!] Распаковка успешно завершена. Все файлы извлечены, manifest.txt отформатирован.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[*] Использование: python OTA_unpacker_full.py <имя_файла_OTA_прошивки.bin>")
        print("    Пример: python OTA_unpacker_full.py ota_A5S13GLY_H201_A6-2026-06-12-19-09_V1_81_49.bin")
    else:
        target_firmware = sys.argv[1]
        unpack_full_firmware(target_firmware)
