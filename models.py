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
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    password_hash = db.Column(db.String(256), nullable=True) 
    
    # 🌟 NOVOS CAMPOS PARA MERCADO PAGO ASSINATURAS 🌟
    mp_preapproval_id = db.Column(db.String(120), nullable=True, unique=True)
    mp_plan_id = db.Column(db.String(120), nullable=True) # ID do plano de preapproval do MP
    plano_assinatura = db.Column(db.String(50), nullable=True) # basico, avancado, premium
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    # 🌟 FIM DOS NOVOS CAMPOS PARA MERCADO PAGO ASSINATURAS 🌟
    
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
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    password_hash = db.Column(db.String(256), nullable=True) 
    
    # NOVO CAMPO: Indica se o usuário precisa trocar a senha na próxima vez que logar
    needs_password_change = db.Column(db.Boolean, default=False) 
    
    # 🌟 NOVO CAMPO: Saldo de Coins para Licitações 🌟
    saldo_coins = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    def set_password(self, password):
        """Hashea e salva a senha."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se a senha em texto puro corresponde ao hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


# ------------------------------------------------------------------------
# 🌟 NOVOS MODELOS PARA O SISTEMA DE LICITAÇÕES E COINS 🌟
# ------------------------------------------------------------------------

class Licitacao(db.Model):
    __tablename__ = 'licitacao'
    
    id = db.Column(db.Integer, primary_key=True)
    condominio_id = db.Column(db.Integer, db.ForeignKey('condominio.id'), nullable=False)
    
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    tipo_servico = db.Column(db.String(100), nullable=False) # Ex: Jardinagem, Segurança...
    
    status = db.Column(db.String(20), default="aberta") # aberta, fechada, cancelada, concluida
    custo_coins = db.Column(db.Integer, default=10) # Custo para uma empresa se candidatar
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    condominio = db.relationship('Condominio', backref=db.backref('licitacoes', lazy=True))
    candidaturas = db.relationship('Candidatura', backref='licitacao', lazy=True)


class Candidatura(db.Model):
    __tablename__ = 'candidatura'
    
    id = db.Column(db.Integer, primary_key=True)
    licitacao_id = db.Column(db.Integer, db.ForeignKey('licitacao.id'), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    
    mensagem = db.Column(db.Text) # Proposta inicial ou apresentação
    preco_estimado = db.Column(db.String(50)) # Opcional
    
    status = db.Column(db.String(20), default="pendente") # pendente, aceita, rejeitada
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    empresa = db.relationship('Empresa', backref=db.backref('candidaturas', lazy=True))


class TransacaoCoin(db.Model):
    """
    Registra histórico de compra de coins (Entrada) ou gasto em licitação (Saída)
    """
    __tablename__ = 'transacao_coin'
    
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    
    quantidade = db.Column(db.Integer, nullable=False) # Positivo (compra) ou Negativo (uso)
    descricao = db.Column(db.String(255)) # Ex: "Compra via MercadoPago", "Candidatura Licitação #5"
    
    payment_id = db.Column(db.String(100), nullable=True) # ID do pagamento no MP (se houver)
    status = db.Column(db.String(20), default="concluido") # pendente, aprovado, concluido
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    empresa = db.relationship('Empresa', backref=db.backref('transacoes', lazy=True))