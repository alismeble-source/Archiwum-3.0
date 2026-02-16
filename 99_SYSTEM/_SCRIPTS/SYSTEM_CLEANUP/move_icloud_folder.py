import shutil
from pathlib import Path

src = Path(r"C:\Users\alimg\iCloudDrive\AlisMeble baza dokumentów_")
dst = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\03_FINANSE\_INBOX\AlisMeble baza dokumentów_")

if src.exists():
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Копирование через Python (поддерживает Unicode лучше)
        total_files = sum(1 for _ in src.rglob('*'))
        copied = 0
        failed = 0
        
        print(f"Копирование {total_files} файлов...")
        
        for item in src.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(src)
                dst_file = dst / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(item, dst_file)
                    copied += 1
                except Exception as e:
                    print(f"  Ошибка: {rel_path} - {e}")
                    failed += 1
                if (copied + failed) % 50 == 0:
                    print(f"  Скопировано: {copied}/{total_files}")
        
        print(f"\nИтого: {copied} скопировано, {failed} ошибок")
        
        # Удалить исходник
        print("Удаление исходника...")
        shutil.rmtree(src)
        print("✓ Успешно перемещено!")
    except Exception as e:
        print(f"✗ Критическая ошибка: {e}")
else:
    print(f"✗ Папка не найдена: {src}")
