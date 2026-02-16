#!/usr/bin/env python3
"""
Очистка кэшей браузера и временных файлов
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

def get_size_mb(path):
    """Получить размер папки в МБ"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_size_mb(entry.path)
    except PermissionError:
        pass
    return total / (1024 * 1024)

def cleanup_cache(path, dry_run=True):
    """Очистить папку кэша"""
    if not Path(path).exists():
        return 0, 0
    
    try:
        size_before = get_size_mb(path)
        
        if not dry_run:
            for item in Path(path).iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except (PermissionError, OSError):
                    pass
        
        size_after = get_size_mb(path) if dry_run else 0
        freed = size_before - size_after
        
        return freed, size_before
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        return 0, 0

def main():
    DRY_RUN = False  # True для preview, False для реального удаления
    
    cleanup_targets = [
        ("Chrome Cache", r"C:\Users\alimg\AppData\Local\Google\Chrome\User Data\Default\Cache"),
        ("Chrome Code Cache", r"C:\Users\alimg\AppData\Local\Google\Chrome\User Data\Default\Code Cache\js"),
        ("Edge Cache", r"C:\Users\alimg\AppData\Local\Microsoft\Edge\User Data\Default\Cache"),
        ("Firefox Cache", r"C:\Users\alimg\AppData\Local\Mozilla\Firefox\Profiles\*/cache2"),
        ("Temp Files", r"C:\Users\alimg\AppData\Local\Temp"),
        ("Windows Temp", r"C:\Windows\Temp"),
        ("Blitz Cache", r"C:\Users\alimg\AppData\Local\Blitz\Saved\PersistentDownloadDir"),
        ("Downloads Old", r"C:\Users\alimg\Downloads"),
    ]
    
    print("=" * 60)
    print("  ОЧИСТКА КЭШЕЙ И ВРЕМЕННЫХ ФАЙЛОВ")
    print("=" * 60)
    print(f"Режим: {'DRY RUN (preview)' if DRY_RUN else 'РЕАЛЬНОЕ УДАЛЕНИЕ'}\n")
    
    total_freed = 0
    total_before = 0
    
    for name, path in cleanup_targets:
        freed, before = cleanup_cache(path, dry_run=DRY_RUN)
        
        if before > 0:
            print(f"✓ {name}")
            print(f"  Размер: {before:.1f} MB")
            print(f"  Освобождается: {freed:.1f} MB")
            total_freed += freed
            total_before += before
    
    print("\n" + "=" * 60)
    print(f"ВСЕГО К ОСВОБОЖДЕНИЮ: {total_freed:.1f} MB ({total_freed/1024:.2f} GB)")
    print(f"ВСЕГО В КЭШАХ: {total_before:.1f} MB ({total_before/1024:.2f} GB)")
    print("=" * 60)
    
    if DRY_RUN:
        print("\n⚠️  РЕЖИМ PREVIEW - ничего не удалено")
        print("Для реального удаления измени DRY_RUN = False в скрипте")
    else:
        print("\n✓ Очистка завершена!")

if __name__ == "__main__":
    main()
