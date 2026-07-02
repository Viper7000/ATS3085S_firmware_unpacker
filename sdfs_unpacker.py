print("==============================================")
print("СТАРТ ПРОГРАММЫ: Инициализация распаковщика...")
print("==============================================")

import os
import sys
import struct
import io
import lz4.block
import re
import string
from PIL import Image
from collections import Counter
from pathlib import Path

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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[*] Использование: python sdfs_unpacker.py <sdfs_*.bin>")
        print("    Пример: python sdfs_unpacker.py sdfs_a.bin")
        exit()
    else:
        file_path = sys.argv[1]
        output_dir = Path(file_path).stem + "_extracted"
        map_output = Path(file_path).stem + "_map.txt"
		
if not os.path.exists(file_path):
    print(f"Ошибка: Исходный файл ресурсов '{file_path}' не найден!")
    exit()

# Проверяем имя по маске sdfs_*.bin (независимо от регистра)
if not re.match(r'^sdfs(_.)?\.bin$', file_path.lower()):
    print(f"Ошибка: Исходный файл не sdfs формата!")
    exit()

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Создана папка: {output_dir}")
    
stats_success = 0
stats_errors = 0
stats_skipped = 0
successful_formats = Counter()
container_file_count = 0

with open(file_path, "rb") as f, open(map_output, "w", encoding="utf-8") as map_f:
    
    block_index = 1
    fw_data = f.read()
    # entry = fw_data[0x0 : 32]
    # file_offset = struct.unpack('<I', entry[16:20])[0]
    file_size = struct.unpack('<I', fw_data[16:20])[0]
    
    if file_size >= 32 and is_valid_name_struct(fw_data[0:12]):
        container_file_count = struct.unpack('<I', fw_data[12:16])[0]

    sub_offset = 0x20
    for _ in range(container_file_count):
        sub_entry = fw_data[sub_offset : sub_offset + 32]
        if len(sub_entry) < 32:
            break
            
        inner_name = clean_string(sub_entry[0:12])
        inner_offset = struct.unpack('<I', sub_entry[12:16])[0]
        inner_size = struct.unpack('<I', sub_entry[16:20])[0]
            
        if not inner_name:
            sub_offset += 32
            continue
            
        # Логируем в manifest.txt со стрелочкой и новым сквозным выравниванием колонок
        prefix_name = f"{inner_name}"
        map_f.write(format_manifest_line(prefix_name, hex(inner_offset), hex(inner_size)))
        print(f"Распакован {inner_name}")       
        
        # Извлекаем и сохраняем подфайл во вложенную папку
        inner_payload = fw_data[inner_offset : inner_offset + inner_size]
        inner_file_path = os.path.join(output_dir, inner_name)
        with open(inner_file_path, 'wb') as inf:
            inf.write(inner_payload)
            
        sub_offset += 32
        block_index += 1

    total_blocks = block_index - 1
    stats_text = (
        "\n"
        f"# Всего распаковано файлов:  {total_blocks}\n"
    )

    map_f.write(stats_text)
    print(stats_text.replace("#", "").replace("   -", "  -"))
