import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Railway: usa volume persistente em /data se disponível
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '')
if RAILWAY_VOLUME:
    DATABASE = os.path.join(RAILWAY_VOLUME, 'escola.db')
else:
    DATABASE = os.path.join(BASE_DIR, 'data', 'escola.db')

SECRET_KEY = os.environ.get('SECRET_KEY', 'escola_eeg_secret_key_2026')
PORT = int(os.environ.get('PORT', 5000))
