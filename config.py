import os
from urllib.parse import quote

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
    
    # Usar SQLite temporariamente para evitar problemas de encoding
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site_condominio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuracao de E-MAIL: Lê as variáveis do .env
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    # MAIL_USE_TLS deve ser True para a porta 587
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True" 
    
    # BUSCANDO o NOME da variavel no .env (CORREÇÃO DE SINTAXE)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False") == "True"
    
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@localhost")
    # Usa o valor de ADMIN_PASSWORD do .env (que DEVE ser o HASH agora)
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD", "admin123")