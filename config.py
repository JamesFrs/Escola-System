import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'data', 'escola.db')
SECRET_KEY = os.environ.get('SECRET_KEY', 'escola_eeg_secret_key_2026')
PORT = int(os.environ.get('PORT', 5000))
