import os
from urllib.parse import quote, urlparse
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
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site_condominio.db' #os.getenv("DATABASE_URL", 'sqlite:///site_condominio.db')
    
    # CORREÇÃO DE ESQUEMA: Altera o esquema de 'postgres://' (se o Render usar) para 'postgresql://' (exigido pelo SQLAlchemy)
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ------------------------------------------------------------------------
    # --- 3. CREDENCIAIS DE E-MAIL (Flask-Mail com Hostinger/SMTP) ---
    # ------------------------------------------------------------------------
    
    # Lida do .env (smtp.hostinger.com)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.hostinger.com")
    # Lida do .env (465)
    MAIL_PORT = int(os.getenv("MAIL_PORT", 465))
    
    # ATUALIZAÇÃO: Para a porta 465 (SSL), desativamos o TLS
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "False") == "True" 
    # NOVO: Ativa o SSL para a porta 465
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "True") == "True" 
    
    # Lida do .env (contato@condblindado.com.br)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "administrador@condblindado.com.br") 
    
    # Lida do .env (sua senha de email do Hostinger)
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "Sp@ce1200") 

    # Variável para armazenar o e-mail REMETENTE VERIFICADO 
    MAIL_USERNAME_SENDER = os.getenv("MAIL_USERNAME_SENDER", "administrador@condblindado.com.br") 
    
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False") == "True"
    
    # --- 4. CREDENCIAIS FINAIS DO ADMINISTRADOR ---
    
    # Lidas do ambiente do Render/OS
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@condominio.com") 
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD", "scrypt:32768:8:1$YXCQXRQWE8Oaiqut$44452ef6ceaae5888045a13e18a6524252e1b4de33b320989a12ed04a3314a8dfae9f1a659ba692a851a26744179ceaea253999e2a60baa8338109d1bd1a1b03")
    
    # --- 5. CONFIGURAÇÕES STRIPE ---
    STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "pk_test_...")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_...")
    STRIPE_PRICE_ID_MONTHLY = os.getenv("STRIPE_PRICE_ID_MONTHLY", "price_...")

    # --- 6. CONFIGURAÇÕES MERCADO PAGO ---
    # Obtenha o Access Token em: https://www.mercadopago.com.br/developers/panel
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "TEST-...") 
    # Token de verificação do Webhook (opcional, mas recomendado para segurança)
    MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
        
        # URL Base da aplicação para gerar links externos
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")    
    # --- Adicionado para forçar o domínio correto na geração de URLs externas ---
    # Extrai o esquema e o nome do servidor da BASE_URL para SERVER_NAME e PREFERRED_URL_SCHEME
    _parsed_url = urlparse(BASE_URL)
    SERVER_NAME = _parsed_url.netloc.split(':')[0] if ':' in _parsed_url.netloc else _parsed_url.netloc
    PREFERRED_URL_SCHEME = _parsed_url.scheme
    # --- Fim das configurações de URL externa ---
