#!/usr/bin/env python3
"""
Умная деduplication с интерактивными фильтрами
Выбирает лучшую копию из каждой группы дублей
"""

import json
import os
import hashlib
from pathlib import Path
from PIL import Image
from collections import defaultdict
from datetime import datetime

PHOTO_DIRS = [
    Path(r"C:\Google_foto\EXPORT_TO_DROPBOX"),
    Path(r"C:\Google_foto\EXPORT_TO_DROPBOX1"),
    Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP"),
]

METADATA_CACHE = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\PHOTO_METADATA_CACHE.json")
OUTPUT_REPORT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\DEDUP_CANDIDATES.csv")

def get_image_quality(filepath):
    """Вернуть качество фото: (разрешение, размер, формат)"""
    try:
        img = Image.open(filepath)
        width, height = img.size
        filesize = filepath.stat().st_size
        fmt = img.format
        return (width * height, filesize, fmt)  # (мегапиксели, размер_байты, формат)
    except Exception:
        return (0, 0, "UNKNOWN")

def calculate_sha256(filepath):
    """Подсчитать SHA256"""
    sha = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return None

def build_duplicate_groups():
    """Найти группы дублей по SHA256"""
    print("🔍 Сканирование фото...")
    
    hash_map = defaultdict(list)
    total_files = 0
    
    for photo_dir in PHOTO_DIRS:
        if not photo_dir.exists():
            continue
        
        for photo_file in photo_dir.rglob('*'):
            if not photo_file.is_file():
                continue
            
            if photo_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp4', '.mov']:
                continue
            
            total_files += 1
            sha = calculate_sha256(photo_file)
            if sha:
                hash_map[sha].append(str(photo_file))
            
            if total_files % 100 == 0:
                print(f"  Обработано: {total_files} файлов...")
    
    # Оставить только дубли (группы > 1)
    duplicates = {sha: files for sha, files in hash_map.items() if len(files) > 1}
    
    print(f"✓ Всего файлов: {total_files}")
    print(f"✓ Уникальных: {len(hash_map)}")
    print(f"✓ Групп дублей: {len(duplicates)}")
    
    return duplicates

def choose_best_file(group):
    """Выбрать лучшую копию из группы по качеству/размеру"""
    
    # Оценить каждый файл
    scored = []
    for filepath in group:
        path_obj = Path(filepath)
        resolution, filesize, fmt = get_image_quality(filepath)
        
        # Приоритет: 1) разрешение 2) размер 3) новизна
        mtime = path_obj.stat().st_mtime
        score = (resolution, filesize, mtime)  # Кортеж для сравнения
        
        scored.append((filepath, score, resolution, filesize, fmt))
    
    # Отсортировать по оценке (лучший = последний)
    scored.sort(key=lambda x: x[1])
    best = scored[-1]
    
    return best[0], scored

def generate_dedup_report(duplicates):
    """Создать отчет с рекомендациями"""
    
    print("\n📝 Генерирую отчет...n")
    
    lines = [
        "SHA256,Лучшая_копия,Разрешение_px,Размер_MB,Формат,Дубли_в_группе,Экономия_MB",
    ]
    
    total_savings = 0
    total_groups = len(duplicates)
    
    for idx, (sha, group) in enumerate(duplicates.items(), 1):
        best_file, scored = choose_best_file(group)
        best_res, best_size, best_fmt = None, None, None
        
        for filepath, score, res, size, fmt in scored:
            if filepath == best_file:
                best_res, best_size, best_fmt = res, size, fmt
                break
        
        # Считать экономию
        other_files = [f for f in group if f != best_file]
        savings = sum(Path(f).stat().st_size for f in other_files) / (1024 * 1024)
        total_savings += savings
        
        # Форматировать строку
        line = f"{sha[:8]},{Path(best_file).name},{best_res},{best_size/1024/1024:.1f},{best_fmt},{len(group)},{savings:.1f}"
        lines.append(line)
        
        if (idx % 50) == 0:
            print(f"  Обработано: {idx}/{total_groups}")
    
    # Записать отчет
    with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"\n✓ Отчет: {OUTPUT_REPORT}")
    print(f"✓ Возможная экономия: {total_savings:.1f} MB ({total_savings/1024:.2f} GB)")
    print(f"✓ Групп дублей: {total_groups}")
    
    return OUTPUT_REPORT, total_savings

def main():
    print("=" * 60)
    print("  УМНАЯ DEDUPLICATION С ФИЛЬТРАМИ")
    print("=" * 60)
    
    duplicates = build_duplicate_groups()
    
    if not duplicates:
        print("✓ Дублей не найдено!")
        return
    
    report_path, savings = generate_dedup_report(duplicates)
    
    print("\n" + "=" * 60)
    print(f"ФИЛЬТРЫ ВЫБОРА ЛУЧШЕЙ КОПИИ:")
    print("  1️⃣  Разрешение (выше = лучше)")
    print("  2️⃣  Размер файла (больше = лучше)")
    print("  3️⃣  Дата (новее = лучше)")
    print("\nОтчет готов! Смотри:", report_path)
    print("=" * 60)

if __name__ == "__main__":
    main()
