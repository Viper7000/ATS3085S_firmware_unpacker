print("=============================================")
print("СТАРТ ПРОГРАММЫ: Инициализация распаковщика...")
print("=============================================")

import os
import sys
import struct
import io
import lz4.block
from PIL import Image
from collections import Counter
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[*] Использование: python res_unpacker.py <имя_файла_ресурсов>")
        print("    Пример: python res_unpacker.py sec_res")
    else:
        file_path = sys.argv[1]
        output_dir = Path(file_path).stem + "_extracted"
        map_output = Path(file_path).stem + "_map.txt"
		
if not os.path.exists(file_path):
    print(f"Ошибка: Исходный файл ресурсов '{file_path}' не найден!")
    exit()

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Создана папка: {output_dir}")
    
stats_success = 0
stats_errors = 0
stats_skipped = 0
successful_formats = Counter()

with open(file_path, "rb") as f, open(map_output, "w", encoding="utf-8") as map_f:
    
    block_index = 1
    
    while True:
        current_offset = f.tell()
        header_bytes = f.read(16)
        if len(header_bytes) < 16:
            print(f"\nДостигнут конец файла (Смещение: {hex(current_offset)}). Распаковка завершена.")
            break
            
        # Извлекаем байты заголовка как независимые числа uint8 через struct
        fmt_type, is_compressed = struct.unpack("<BB", header_bytes[0:2])
        
        # Читаем 3 байта несжатого размера
        uncompressed_size = struct.unpack("<I", header_bytes[2:5] + b'\x00')[0]
        
        # Извлекаем байты разрешения как числа для 12-битного декодирования
        b5, b6, b7 = struct.unpack("<BBB", header_bytes[5:8])
        height = ((b6 & 0x0F) << 8) | b5
        width = (b7 << 4) | (b6 >> 4)
        
        # Читаем 3 байта сжатого размера
        compressed_size = struct.unpack("<I", header_bytes[8:11] + b'\x00')[0]
        
        # Запись карты СТРОГО по вашему шаблону: название (таб) Тип: хх (таб) Сжатие: да/нет
        comp_text = "да" if is_compressed == 1 else "нет"
        map_f.write(f"image_{block_index:03d}.png\tТип:{fmt_type}\tСжатие: {comp_text}\n")
        
        if is_compressed == 0 or compressed_size == 0:
            read_size = uncompressed_size
        else:
            read_size = compressed_size
        
        # Полный детальный лог каждого блока
        print(f"\nБлок {block_index}: Формат={fmt_type}, Сжатие={is_compressed}, Смещение={hex(current_offset)}, Размер={width}x{height}")
        print(f"  Будет прочитано из файла: {read_size} байт, Сжатый: {compressed_size} байт, Несжатый: {uncompressed_size} байт")
        
        payload = f.read(read_size)
        if len(payload) != read_size:
            print(f"  Ошибка: файл неожиданно оборвался на блоке {block_index}.")
            stats_errors += 1
            break
            
        KNOWN_IMAGE_FORMATS = {3, 9, 71, 72, 73, 74, 75}
        if fmt_type not in KNOWN_IMAGE_FORMATS:
            print(f"  [Пропуск] Формат {fmt_type} не является поддерживаемым типом изображения.")
            stats_skipped += 1
            block_index += 1
            continue
            
        # Безопасная декомпрессия
        if is_compressed == 1 and compressed_size > 0:
            try:
                decompressed_data = lz4.block.decompress(payload, uncompressed_size=uncompressed_size)
            except Exception as e:
                print(f"  Ошибка декомпрессии LZ4 в блоке {block_index}: {e}")
                stats_errors += 1
                block_index += 1
                continue
        else:
            decompressed_data = payload
            
        output_path = os.path.join(output_dir, f"image_{block_index:03d}.png")
        
        try:
            if fmt_type == 3 or fmt_type == 9:
                img = Image.open(io.BytesIO(decompressed_data))
                img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            elif fmt_type == 71:
                img = Image.frombytes('RGBA', (width, height), decompressed_data, 'raw', 'BGRA')
                img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            elif fmt_type == 72:
                rgba_pixels = bytearray()
                for i in range(0, width * height * 3, 3):
                    if i + 2 >= len(decompressed_data):
                        rgba_pixels.extend([0, 0, 0, 255])
                        continue
                    pixel_16bit = struct.unpack("<H", decompressed_data[i:i+2])[0]
                    alpha = decompressed_data[i+2]
                    
                    # Декодирование RGB565
                    r = ((pixel_16bit & 0xF800) >> 11) * 255 // 31
                    g = ((pixel_16bit & 0x07E0) >> 5) * 255 // 63
                    b = (pixel_16bit & 0x001F) * 255 // 31
                    rgba_pixels.extend([r, g, b, alpha])
                    
                final_img = Image.frombytes('RGBA', (width, height), bytes(rgba_pixels))
                final_img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            elif fmt_type == 73:
                rgb_pixels = bytearray()
                for i in range(0, width * height * 2, 2):
                    if i + 1 >= len(decompressed_data):
                        rgb_pixels.extend([0, 0, 0])
                        continue
                    pixel_16bit = struct.unpack("<H", decompressed_data[i:i+2])[0]
                    
                    r = ((pixel_16bit & 0xF800) >> 11) * 255 // 31
                    g = ((pixel_16bit & 0x07E0) >> 5) * 255 // 63
                    b = (pixel_16bit & 0x001F) * 255 // 31
                    rgb_pixels.extend([r, g, b])
                    
                final_img = Image.frombytes('RGB', (width, height), bytes(rgb_pixels))
                final_img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            elif fmt_type == 74:
                rgba_pixels = bytearray()
                for i in range(0, width * height * 2, 2):
                    if i + 1 >= len(decompressed_data):
                        rgba_pixels.extend([0, 0, 0, 255])
                        continue
                    pixel_16bit = struct.unpack("<H", decompressed_data[i:i+2])[0]
                    
                    a = 255 if (pixel_16bit & 0x8000) else 0
                    r = ((pixel_16bit & 0x7C00) >> 10) * 255 // 31
                    g = ((pixel_16bit & 0x03E0) >> 5) * 255 // 31
                    b = (pixel_16bit & 0x001F) * 255 // 31
                    rgba_pixels.extend([r, g, b, a])
                    
                final_img = Image.frombytes('RGBA', (width, height), bytes(rgba_pixels))
                final_img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            elif fmt_type == 75:
                palette_data = decompressed_data[:1024]
                pixel_data = decompressed_data[1024:]
                expected_pixel_len = width * height
                
                pixel_data = pixel_data.ljust(expected_pixel_len, b'\x00')[:expected_pixel_len]
                
                palette_rgba_list = []
                for i in range(0, 1024, 4):
                    b_chan, g_chan, r_chan, a_chan = palette_data[i:i+4]
                    palette_rgba_list.append(bytes([r_chan, g_chan, b_chan, a_chan]))
                    
                rgba_pixels = bytearray(expected_pixel_len * 4)
                for idx, pixel_idx in enumerate(pixel_data):
                    p_idx = pixel_idx if pixel_idx < 256 else 0
                    rgba_pixels[idx*4 : idx*4+4] = palette_rgba_list[p_idx]
                    
                final_img = Image.frombytes('RGBA', (width, height), bytes(rgba_pixels))
                final_img.save(output_path, "PNG")
                print(f"  [Успех] Сохранено: {output_path}")

            stats_success += 1
            successful_formats[fmt_type] += 1

        except Exception as img_err:
            print(f"  Ошибка сборки графики для формата {fmt_type}: {img_err}")
            stats_errors += 1
        
        block_index += 1

    # Формируем текст статистики строго по вашему шаблону с префиксом #
    total_blocks = block_index - 1
    stats_text = (
        "\n"
        "#==================================================\n"
        "# СТАТИСТИКА РАСПАКОВКИ\n"
        "#==================================================\n"
        f"# Всего обработано записей:  {total_blocks}\n"
        f"# Успешно извлечено:         {stats_success}\n"
        f"# Ошибок:                    {stats_errors}\n"
        f"# Пропущено (другие типы):   {stats_skipped}\n"
        f"# Файл карты сохранен как:   {map_output}\n"
        "#--------------------------------------------------\n"
    )
    for fmt, count in sorted(successful_formats.items()):
        stats_text += f"#   - Формат {fmt:02d}: {count} блоков\n"
    stats_text += "#==================================================\n"

    map_f.write(stats_text)
    print(stats_text.replace("#", "").replace("   -", "  -"))
