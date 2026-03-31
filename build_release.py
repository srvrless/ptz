import subprocess
import shutil
import hashlib
from pathlib import Path


def file_hash(path: Path) -> str:
    """Считает хэш файла"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def build():
    release_dir = Path("./dist_release")
    wheels_dir = release_dir / "wheels"

    cache_dir = Path("./.cache_wheels")
    cache_dir.mkdir(exist_ok=True)

    # Хэш зависимостей (можно расширить при необходимости)
    deps_hash = file_hash(Path("pyproject.toml")) + file_hash(Path("uv.lock"))
    deps_hash = hashlib.sha256(deps_hash.encode()).hexdigest()

    cached_wheels = cache_dir / deps_hash

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()

    print("[*] Компиляция зависимостей...")
    subprocess.run(
        ["uv", "pip", "compile", "pyproject.toml", "-o", "requirements.txt"],
        check=True
    )

    if cached_wheels.exists():
        print("[*] Используем кешированные зависимости...")
        shutil.copytree(cached_wheels, wheels_dir)
    else:
        print("[*] Скачивание wheel-файлов...")
        subprocess.run([
            "uv", "run", "--active", "pip", "download",
            "-r", "requirements.txt",
            "--dest", str(wheels_dir)
        ], check=True)

        print("[*] Сохраняем зависимости в кеш...")
        shutil.copytree(wheels_dir, cached_wheels)

    print("[*] Копирование исходного кода...")
    shutil.copytree("./app", release_dir / "app")
    shutil.copy("pyproject.toml", release_dir / "pyproject.toml")
    shutil.copy("uv.lock", release_dir / "uv.lock")

    # Удаляем временный файл
    Path("requirements.txt").unlink()

    print(f"\n[УСПЕХ] Всё готово в папке: {release_dir}")
    print("Теперь просто запакуй её в .zip и отправляй на сервер.")


if __name__ == "__main__":
    build()