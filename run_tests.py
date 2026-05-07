#!/usr/bin/env python
"""
Скрипт для запуска тестов с подсчётом покрытия.
Аналог: python manage.py test tests/ --verbosity=2
"""
import os
import sys
import subprocess

def main():
    print("=" * 60)
    print("ЗАПУСК АВТОМАТИЗИРОВАННЫХ ТЕСТОВ")
    print("=" * 60)
    
    # Запускаем тесты
    result = subprocess.run(
        [sys.executable, 'manage.py', 'test', 'tests/', '--verbosity=2'],
        capture_output=False
    )
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())