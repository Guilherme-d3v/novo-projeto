import enum
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.dialects.postgresql import ENUM

db = SQLAlchemy()

# Define the CondominioRank Enum
class CondominioRank(enum.Enum):
    BRONZE = "bronze"
    PRATA = "prata"
    OURO = "ouro"

class Condominio(db.Model):
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False)
    tipo = db.Column(db.String(50))
    unidades = db.Column(db.Integer)
    cep = db.Column(db.String(9))
    endereco = db.Column(db.String(200))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    contato_nome = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    whatsapp = db.Column(db.String(20))
    nivel = db.Column(db.String(50))
    objetivo = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0)
    pdf_filename = db.Column(db.String(300))
    status = db.Column(db.String(20), default="pendente")
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    password_hash = db.Column(db.String(256), nullable=True) 
    
    # 🌟 NOVOS CAMPOS PARA STRIPE 🌟
    stripe_customer_id = db.Column(db.String(120), nullable=True, unique=True)
    stripe_subscription_id = db.Column(db.String(120), nullable=True, unique=True)
    subscription_status = db.Column(db.String(50), default='inativo') # active, past_due, canceled, inativo
    # 🌟 FIM DOS NOVOS CAMPOS PARA STRIPE 🌟
    
    # NOVO CAMPO: Indica se o usuário precisa trocar a senha na próxima vez que logar
    needs_password_change = db.Column(db.Boolean, default=False) 

    # Novo campo para o ranking
    rank = db.Column(ENUM(CondominioRank, name="condominiorank", schema="public"), nullable=True) # Rank assigned on approval
    
    def set_password(self, password):
        """Hashea e salva a senha."""
        self.password_hash = generate_password_hash(password) 

    def check_password(self, password):
        """Verifica se a senha em texto puro corresponde ao hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False)
    categorias = db.Column(db.Text)
    descricao = db.Column(db.Text)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    cep = db.Column(db.String(9))
    endereco = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    email_comercial = db.Column(db.String(100))
    website = db.Column(db.String(200))
    doc_filename = db.Column(db.String(300))
    status = db.Column(db.String(20), default="pendente")
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    password_hash = db.Column(db.String(256), nullable=True) 
    
    # NOVO CAMPO: Indica se o usuário precisa trocar a senha na próxima vez que logar
    needs_password_change = db.Column(db.Boolean, default=False) 
    
    def set_password(self, password):
        """Hashea e salva a senha."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se a senha em texto puro corresponde ao hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)