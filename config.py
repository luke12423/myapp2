import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ваш-секретный-ключ-здесь'

    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Загрузка файлов
    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    # Сессии
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Пагинация
    ITEMS_PER_PAGE = 12