import os
from urllib.parse import quote
from dotenv import load_dotenv

# Garantir que as variáveis de ambiente sejam carregadas, embora já esteja em app.py
load_dotenv() 

class Config:
    # --- 1. CONFIGURAÇÕES DE APLICAÇÃO ---
    
    # LÊ a SECRET_KEY do ambiente do Render/OS, com fallback para dev-key
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
    
    # --- 2. CONFIGURAÇÕES DO BANCO DE DADOS (NEON) ---
    
    # PRIORIZA a DATABASE_URL do ambiente (que será o Neon no Render)
    # Usa SQLite como fallback APENAS para desenvolvimento local, se não houver a var.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", 'sqlite:///site_condominio.db')
    
    # CORREÇÃO DE ESQUEMA: Altera o esquema de 'postgres://' (se o Render usar) para 'postgresql://' (exigido pelo SQLAlchemy)
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- 3. CREDENCIAIS DE E-MAIL (Flask-Mail com SendGrid) ---
    
    # O SendGrid usa estas configurações padrão de SMTP:
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.sendgrid.net")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True" 
    
    # No SendGrid, o USERNAME é FIXO como 'apikey'
    MAIL_USERNAME = os.getenv("MAIL_USERNAME_SMTP", "apikey") 
    
    # O PASSWORD é a Chave de API COMPLETA do SendGrid (lida da variável SENDGRID_API_KEY)
    # NOTA: O Flask-Mail lida com esta chave como a senha.
    MAIL_PASSWORD = os.getenv("SENDGRID_API_KEY", "SUA_CHAVE_DE_API_DO_SENDGRID_AQUI") 

    # Variável para armazenar o e-mail REMETENTE VERIFICADO (Seu e-mail pessoal para testes)
    MAIL_USERNAME_SENDER = os.getenv("MAIL_USERNAME_SENDER", "seu.email.teste@gmail.com") 
    
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False") == "True"
    
    # --- 4. CREDENCIAIS FINAIS DO ADMINISTRADOR ---
    
    # Lidas do ambiente do Render/OS
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@condominio.com") 
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD", "scrypt:32768:8:1$N53bJ90jJlErEUS9$102868c4f9a054fa2aca6ad53090cc6f455b501d3e6d6cbecb246d06a7db2e6792916b58b8dfef529646e3d15f30723a7b97a5f4ff13f7a85cb7556884fbba0a")
