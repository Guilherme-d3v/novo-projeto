import os
from urllib.parse import quote

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
    
    # Usar SQLite temporariamente para evitar problemas de encoding
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site_condominio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 25))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "False") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False") == "True"
    
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@localhost")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")