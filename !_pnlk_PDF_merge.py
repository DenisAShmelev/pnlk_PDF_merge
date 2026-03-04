import os
import glob
import re
import shutil
import warnings
import sys
from PyPDF2 import PdfMerger
from datetime import datetime

# Полностью отключаем все предупреждения
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# Класс для подавления stderr
class SuppressStderr:
    def __enter__(self):
        self._original_stderr = sys.stderr
        self._devnull = open(os.devnull, 'w')
        sys.stderr = self._devnull
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._devnull.close()
        sys.stderr = self._original_stderr

def create_timestamp_directory():
    """
    Создает папку с текущей датой и временем и возвращает ее путь
    """
    # Форматируем дату и время: ГГГГ.ММ.ДД_ЧЧ-ММ-СС
    timestamp = datetime.now().strftime("%Y.%m.%d_%H-%M-%S")
    timestamp_dir = os.path.join(os.getcwd(), f"обработка_{timestamp}")
    
    try:
        os.makedirs(timestamp_dir, exist_ok=True)
        print(f"📁 Создана папка с временной меткой: {timestamp_dir}")
        return timestamp_dir
    except Exception as e:
        print(f"❌ Ошибка при создании папки с временной меткой: {e}")
        # В случае ошибки используем текущую директорию
        return os.getcwd()

def process_pdf_files():
    """
    Обрабатывает PDF-файлы:
    - Объединяет файлы с одинаковым префиксом (если их > 1 и номера от 1 до 100)
    - Копирует одиночные файлы в папку "готовые ранее" с оригинальным именем
    """
    # Определяем текущую рабочую директорию
    current_dir = os.getcwd()
    print(f"📁 Работаем в директории: {current_dir}")
    
    # Создаем папку с временной меткой
    timestamp_dir = create_timestamp_directory()
    
    # Создаем папки для результатов внутри папки с временной меткой
    output_dir = os.path.join(timestamp_dir, "Объединенные")
    single_files_dir = os.path.join(timestamp_dir, "Одиночные")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(single_files_dir, exist_ok=True)
    
    print(f"📂 Создана папка для объединенных файлов: {output_dir}")
    print(f"📂 Создана папка для одиночных файлов: {single_files_dir}")
    
    # Получаем все PDF-файлы в текущей директории
    pdf_files = glob.glob("*.pdf")
    
    if not pdf_files:
        print("❌ PDF-файлы не найдены в текущей директории.")
        return 0, 0, timestamp_dir
    
    print(f"📄 Найдено PDF-файлов: {len(pdf_files)}")
    
    # Группируем файлы по общей начальной части (до последнего дефиса с номером)
    file_groups = {}
    
    for pdf_file in pdf_files:
        # Ищем шаблон: любое количество символов + дефис + число + .pdf
        match = re.match(r'^(.+)-(\d+)\.pdf$', pdf_file)
        if match:
            base_name = match.group(1)  # Начальная часть имени
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append(pdf_file)
        else:
            # Файлы не соответствующие шаблону тоже обрабатываем как одиночные
            base_name = pdf_file[:-4]  # Убираем .pdf
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append(pdf_file)
    
    if not file_groups:
        print("❌ Не удалось сгруппировать файлы.")
        return 0, 0, timestamp_dir
    
    print(f"🔍 Обнаружено групп файлов: {len(file_groups)}")
    
    # Обрабатываем группы файлов
    merged_count = 0
    copied_count = 0
    
    for base_name, files in file_groups.items():
        # Проверяем, соответствует ли группа нашему шаблону (есть ли номера)
        has_numbered_files = any(re.match(r'^.+-\d+\.pdf$', f) for f in files)
        
        if len(files) > 1 and has_numbered_files:
            # Проверяем, что все файлы имеют номера в диапазоне [1-100] и начинаются с 1
            if validate_numbered_files(files):
                # Объединяем файлы группы (если они прошли валидацию)
                merged_count += process_group_merge(base_name, files, output_dir)
            else:
                # Если не прошли валидацию, копируем как одиночные
                print(f"\n⚠️ Группа '{base_name}' не прошла валидацию (номера должны быть от 1 до 100 и начинаться с 1).")
                for pdf_file in files:
                    copied_count += process_single_file(pdf_file, single_files_dir)
        else:
            # Копируем одиночный файл с оригинальным именем
            for pdf_file in files:
                copied_count += process_single_file(pdf_file, single_files_dir)
    
    return merged_count, copied_count, timestamp_dir

def validate_numbered_files(files):
    """
    Проверяет, что все файлы в группе:
    1. Имеют номера в диапазоне [1-100]
    2. Номера начинаются с 1 (без пропусков в начале)
    """
    # Извлекаем все номера из файлов
    numbered_files = []
    for f in files:
        match = re.search(r'-(\d+)\.pdf$', f)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 100:
                numbered_files.append((f, num))
            else:
                print(f"   ⚠️ Файл '{f}' имеет номер {num}, который вне диапазона [1-100]")
                return False
        else:
            print(f"   ⚠️ Файл '{f}' не соответствует формату с номером")
            return False
    
    if not numbered_files:
        return False
    
    # Сортируем по номеру
    numbered_files.sort(key=lambda x: x[1])
    
    # Проверяем, что первый номер равен 1
    if numbered_files[0][1] != 1:
        print(f"   ⚠️ Первый номер должен быть 1, но найден {numbered_files[0][1]}")
        return False
    
    # Проверяем, что номера идут последовательно (без пропусков)
    # Это опционально - можно убрать, если нужна только проверка на наличие 1 и диапазон
    expected_num = 1
    for f, num in numbered_files:
        if num != expected_num:
            print(f"   ⚠️ Нарушена последовательность номеров: ожидался {expected_num}, найден {num}")
            return False
        expected_num += 1
    
    return True

def process_group_merge(base_name, files, output_dir):
    """
    Объединяет несколько файлов одной группы
    """
    try:
        # Сортируем файлы по номеру для правильного порядка
        numbered_files = [f for f in files if re.match(r'^.+-\d+\.pdf$', f)]
        if numbered_files:
            numbered_files.sort(key=lambda x: int(re.search(r'-(\d+)\.pdf$', x).group(1)))
            files = numbered_files + [f for f in files if f not in numbered_files]
        
        print(f"\n🔄 Обрабатываем группу '{base_name}' ({len(files)} файлов):")
        for f in files:
            print(f"   ├─ {f}")
        
        # Создаем объект для объединения PDF
        merger = PdfMerger()
        
        # Используем контекстный менеджер для подавления stderr
        with SuppressStderr():
            # Добавляем все файлы группы в объединитель
            for pdf_file in files:
                merger.append(pdf_file)
            
            # Формируем имя выходного файла - используем только базовое имя
            output_filename = f"{base_name}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            
            # Сохраняем объединенный файл
            with open(output_path, 'wb') as output_file:
                merger.write(output_file)
        
        print(f"   └─ ✅ Объединен в: {output_filename}")
        return 1
        
    except Exception as e:
        print(f"   └─ ❌ Ошибка при объединении группы '{base_name}': {e}")
        return 0
    finally:
        try:
            merger.close()
        except:
            pass

def process_single_file(pdf_file, single_files_dir):
    """
    Копирует одиночный файл в папку "готовые ранее" с оригинальным именем
    """
    try:
        # Копируем файл с оригинальным именем
        output_path = os.path.join(single_files_dir, pdf_file)
        shutil.copy2(pdf_file, output_path)
        
        print(f"📋 Одиночный файл скопирован: {pdf_file}")
        return 1
        
    except Exception as e:
        print(f"❌ Ошибка при копировании файла '{pdf_file}': {e}")
        return 0

def wait_for_user():
    """
    Ожидает реакции пользователя перед закрытием консоли
    """
    print("\n" + "="*60)
    print("Программа завершена. Нажмите Enter для выхода...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nВыход...")
    except Exception:
        # Дополнительная обработка на случай проблем с input
        print("\nАвтоматический выход через 5 секунд...")
        import time
        time.sleep(5)

def main():
    """
    Основная функция с улучшенной обработкой ошибок
    """
    try:
        print("🚀 Запуск обработки PDF файлов...")
        print("=" * 50)
        
        merged_count, copied_count, timestamp_dir = process_pdf_files()
        
        print(f"\n{'='*60}")
        print("📊 ИТОГИ РАБОТЫ:")
        print("-" * 30)
        
        if merged_count > 0:
            print(f"✅ Объединено групп файлов: {merged_count}")
        else:
            print(f"➖ Не объединено ни одной группы файлов")
            
        if copied_count > 0:
            print(f"✅ Скопировано одиночных файлов: {copied_count}")
        else:
            print(f"➖ Не скопировано ни одного одиночного файла")
        
        if merged_count == 0 and copied_count == 0:
            print(f"\n😔 Не удалось обработать ни одного файла.")
            print("ℹ️  Проверьте, что файлы имеют формат: 'имя-номер.pdf'")
            print("   Для объединения номера должны быть от 1 до 100 и начинаться с 1")
        else:
            total_processed = merged_count + copied_count
            print(f"\n🎉 Всего обработано: {total_processed} элементов")
            
        print(f"\n📁 Результаты сохранены в папке:")
        print(f"   📂 {timestamp_dir}")
        print(f"   ├─ Объединенные файлы: папка 'Объединенные'")
        print(f"   └─ Одиночные файлы: папка 'Одиночные'")
            
    except KeyboardInterrupt:
        print("\n⏹️ Программа прервана пользователем.")
    except Exception as e:
        print(f"\n💥 Произошла непредвиденная ошибка: {e}")
        print("🔄 Попробуйте запустить программу еще раз.")

if __name__ == "__main__":
    main()
    wait_for_user()