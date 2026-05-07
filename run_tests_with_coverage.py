#!/usr/bin/env python
"""
Скрипт для запуска тестов с оценкой покрытия кода.
Требуется: pip install coverage
"""
import os
import sys
import subprocess

def main():
    print("=" * 60)
    print("ОЦЕНКА ПОКРЫТИЯ КОДА ТЕСТАМИ")
    print("=" * 60)
    
    # Запускаем coverage
    commands = [
        [sys.executable, '-m', 'coverage', 'run', 'manage.py', 'test', 'tests/'],
        [sys.executable, '-m', 'coverage', 'report', '-m'],
        [sys.executable, '-m', 'coverage', 'html'],
    ]
    
    for cmd in commands:
        print(f"\n>> Выполнение: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0 and 'test' in cmd:
            print("⚠ Некоторые тесты не прошли!")
    
    print("\n" + "=" * 60)
    print("Отчёт о покрытии создан в директории htmlcov/")
    print("=" * 60)

if __name__ == '__main__':
    # Установите coverage если ещё не установлен
    try:
        import coverage
    except ImportError:
        print("Устанавливаю coverage...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'coverage'])
    
    main()