import os
import json
import zipfile
import shutil
import subprocess
import urllib.request
from pathlib import Path

import psutil  # pip install psutil
import pika    # pip install pika

# --- КОНФИГУРАЦИЯ ПУТЕЙ (Используем Path для Windows-совместимости) ---
BASE_DIR = Path(r"C:\ptz_infrastructure")
APP_DIR = BASE_DIR / "app"
VENV_DIR = BASE_DIR / "venv"
BAT_FILE = BASE_DIR / "run_ptz.bat"
TEMP_DIR = BASE_DIR / "temp_update"

def kill_ptz_processes():
    target_python = str(VENV_DIR / "Scripts" / "python.exe").lower()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline:
                full_cmd = " ".join(cmdline).lower()
                if target_python in full_cmd:
                    print(f"[!] Завершаем процесс PID {proc.info['pid']}")
                    proc.terminate()
                    proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            proc.kill() # Если не закрылся по-хорошему
        except Exception as e:
            print(f"[!] Ошибка при остановке процесса: {e}")

def process_update(ch, method, properties, body):
    """Основной воркер обновления"""
    try:
        payload = json.loads(body)
        version = payload.get("version", "unknown")
        url = payload.get("url")

        print(f"\n{'='*40}")
        print(f" НАЧАЛО ОБНОВЛЕНИЯ: Версия {version}")
        print(f"{'='*40}")

        # 1. Подготовка временных папок
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        archive_path = TEMP_DIR / "release.zip"
        extract_path = TEMP_DIR / "extracted"

        # 2. Скачивание архива с центрального сервера
        print(f"[*] Скачивание: {url}")
        urllib.request.urlretrieve(url, archive_path)

        # 3. Распаковка
        print("[*] Распаковка архива...")
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 4. Остановка текущего приложения
        kill_ptz_processes()

        # 5. Обновление файлов проекта (pyproject.toml, uv.lock, app/)
        print("[*] Обновление исходного кода и манифестов...")
        
        # Обновляем конфиги uv
        for file_name in ["pyproject.toml", "uv.lock"]:
            src_file = extract_path / file_name
            if src_file.exists():
                shutil.copy2(src_file, BASE_DIR / file_name)

        # Обновляем папку с кодом
        new_app_source = extract_path / "app"
        if new_app_source.exists():
            if APP_DIR.exists():
                shutil.rmtree(APP_DIR)
            shutil.copytree(new_app_source, APP_DIR)

        # 6. Оффлайн синхронизация зависимостей через UV
        print("[*] Запуск UV Sync (Offline mode)...")
        wheels_path = extract_path / "wheels"
        
        # Вызываем: uv pip install --no-index --find-links ./wheels -r pyproject.toml
        # Мы используем 'uv pip install', так как это проще всего для синхронизации в существующий venv
        uv_command = [
            "uv", "pip", "install",
            "--offline",            # Строго оффлайн
            "--no-index",           # Не искать в PyPI
            "--find-links", str(wheels_path),
            "--python", str(VENV_DIR / "Scripts" / "python.exe"),
            "-r", str(BASE_DIR / "pyproject.toml")
        ]

        result = subprocess.run(uv_command, capture_output=True, text=True, check=True)
        print("[V] Библиотеки обновлены успешно.")

        # 7. Запуск новой версии
        print("[*] Перезапуск приложения...")
        if BAT_FILE.exists():
            # Запускаем .bat в новом независимом процессе (чтобы агент не ждал его завершения)
            subprocess.Popen(
                ["cmd.exe", "/c", str(BAT_FILE)],
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        
        print(f"\n[УСПЕХ] Инстанс обновлен до {version} и запущен.")

    except subprocess.CalledProcessError as e:
        print(f"\n[ОШИБКА UV]: {e.stderr}")
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА]: {e}")
    finally:
        # 8. Очистка временных файлов
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print(f"{'='*40}\n")

# --- Настройка RabbitMQ Consumer ---
def start_agent():
    try:
        # Укажи IP сервера с RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters('10.14.101.253'))
        channel = connection.channel()

        channel.exchange_declare(exchange='ptz_updates', exchange_type='fanout')
        
        # Индивидуальная очередь для каждого инстанса
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='ptz_updates', queue=queue_name)

        print(f"[*] Агент запущен. Ожидаю сигналов в очереди {queue_name}...")
        
        channel.basic_consume(queue=queue_name, on_message_callback=process_update, auto_ack=True)
        channel.start_consuming()
    except Exception as e:
        print(f"Ошибка подключения к RabbitMQ: {e}")

if __name__ == "__main__":
    start_agent()