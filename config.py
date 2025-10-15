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
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD", "scrypt:32768:8:1$YXCQXRQWE8Oaiqut$44452ef6ceaae5888045a13e18a6524252e1b4de33b320989a12ed04a3314a8dfae9f1a659ba692a851a26744179ceaea253999e2a60baa8338109d1bd1a1b03")
