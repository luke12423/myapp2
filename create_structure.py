import os


def create_flask_structure():
    # Основные файлы
    files = [
        'app.py',
        'config.py',
        'requirements.txt',
        '.env',
        '.gitignore',
        'run.py'
    ]

    # Папки и подпапки
    folders = [
        'static/css',
        'static/js',
        'static/images',
        'static/uploads',
        'templates/admin'
    ]

    # Файлы в подпапках
    sub_files = {
        'static/css': ['style.css'],
        'static/js': ['main.js'],
        'templates': [
            'base.html', 'index.html', 'news.html',
            'news_detail.html', 'catalog.html', 'about.html',
            'contacts.html', 'login.html', 'register.html',
            '404.html', '500.html'
        ],
        'templates/admin': ['index.html', 'create_news.html']
    }

    print("Создание структуры проекта Flask...")

    # Создаем основные файлы
    for file in files:
        with open(file, 'w', encoding='utf-8') as f:
            if file == '.gitignore':
                f.write("""venv/
__pycache__/
*.pyc
.env
instance/
*.db
*.log
uploads/
""")
            elif file == 'requirements.txt':
                f.write("""Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.2
Flask-WTF==1.1.1
Flask-Migrate==4.0.5
Flask-Admin==1.6.1
python-dotenv==1.0.0
Pillow==10.0.0
""")
            elif file == '.env':
                f.write("""SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///app.db
DEBUG=True
""")
        print(f"✓ Создан файл: {file}")

    # Создаем папки
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"✓ Создана папка: {folder}/")

    # Создаем файлы в подпапках
    for folder, file_list in sub_files.items():
        for file in file_list:
            file_path = os.path.join(folder, file)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("")  # Пустой файл
            print(f"✓ Создан файл: {file_path}")

    print("\n✅ Структура проекта успешно создана!")
    print("Следующие шаги:")
    print("1. cd my_flask_site")
    print("2. python -m venv venv")
    print("3. venv\\Scripts\\activate (Windows) или source venv/bin/activate (Linux/Mac)")
    print("4. pip install -r requirements.txt")
    print("5. Заполните файлы кодом из предыдущих ответов")


if __name__ == "__main__":
    create_flask_structure()