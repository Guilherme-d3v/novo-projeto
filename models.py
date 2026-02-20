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
    lgpd_consent = db.Column(db.Boolean, default=False)
    terms_consent = db.Column(db.Boolean, default=False)
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

    @property
    def subscription_status(self):
        """Calcula o status da assinatura dinamicamente, com atenção aos fusos horários."""
        from datetime import datetime, timezone # Importa o necessário aqui

        if not self.plano_assinatura or not self.subscription_expires_at:
            return 'inactive'
        
        # Garante que estamos comparando datetimes cientes de fuso horário (timezone-aware).
        # Isso evita bugs comuns de fuso horário entre o servidor da aplicação e o do banco de dados.
        
        # Converte a data de expiração (que é 'naive') para uma data 'aware' em UTC
        expires_at_utc = self.subscription_expires_at.replace(tzinfo=timezone.utc)
        
        # Pega a data/hora atual, também ciente de que está em UTC
        now_utc = datetime.now(timezone.utc)

        if expires_at_utc > now_utc:
            return 'active'
            
        return 'inactive'


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
    lgpd_consent = db.Column(db.Boolean, default=False)
    terms_consent = db.Column(db.Boolean, default=False)
    telefone = db.Column(db.String(20))
    email_comercial = db.Column(db.String(100))
    website = db.Column(db.String(200))
    doc_filename = db.Column(db.String(300))
    logo_filename = db.Column(db.String(255), nullable=True)
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

    @property
    def average_rating(self):
        from sqlalchemy.sql import func
        # Retorna a média de avaliações ou None se não houver nenhuma
        avg = db.session.query(func.avg(Avaliacao.rating)).filter(Avaliacao.empresa_id == self.id).scalar()
        return avg if avg is not None else 0

    @property
    def service_count(self):
        # Retorna o número de serviços concluídos (licitações vencidas)
        return Licitacao.query.filter_by(empresa_vencedora_id=self.id, status='concluida').count()
        
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
    
    # NOVO: Campo para armazenar o orçamento da proposta vencedora
    valor_orcamento = db.Column(db.Float, nullable=True)
    
    # NOVO: ID da empresa que venceu a licitação
    empresa_vencedora_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    condominio = db.relationship('Condominio', backref=db.backref('licitacoes', lazy=True))
    candidaturas = db.relationship('Candidatura', backref='licitacao', lazy=True)
    
    # NOVO: Relacionamento com a empresa vencedora
    empresa_vencedora = db.relationship('Empresa', foreign_keys=[empresa_vencedora_id])
    
    # NOVO: Relacionamento com a avaliação (se houver)
    avaliacao = db.relationship('Avaliacao', backref='licitacao', uselist=False, cascade="all, delete-orphan")


class Candidatura(db.Model):
    __tablename__ = 'candidatura'
    
    id = db.Column(db.Integer, primary_key=True)
    licitacao_id = db.Column(db.Integer, db.ForeignKey('licitacao.id'), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    
    mensagem = db.Column(db.Text) # Proposta inicial ou apresentação
    
    # ALTERADO: Mudando de String para Float para permitir cálculos
    valor_proposta = db.Column(db.Float, nullable=True)
    
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


class TransacaoPlano(db.Model):
    """
    Registra o histórico de compras de planos de assinatura pelos condomínios.
    """
    __tablename__ = 'transacao_plano'
    
    id = db.Column(db.Integer, primary_key=True)
    condominio_id = db.Column(db.Integer, db.ForeignKey('condominio.id'), nullable=False)
    
    plano_id = db.Column(db.String(50), nullable=False) # 'basico', 'avancado', 'premium'
    valor = db.Column(db.Float, nullable=False) # O valor efetivamente pago
    
    payment_id = db.Column(db.String(100), nullable=True) # ID do pagamento no MP
    status = db.Column(db.String(20), default="concluido") # pendente, concluido, falhou
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    condominio = db.relationship('Condominio', backref=db.backref('transacoes_plano', lazy=True))

# ------------------------------------------------------------------------
# 🌟 NOVO MODELO PARA AVALIAÇÕES 🌟
# ------------------------------------------------------------------------
class Avaliacao(db.Model):
    __tablename__ = 'avaliacao'
    
    id = db.Column(db.Integer, primary_key=True)
    licitacao_id = db.Column(db.Integer, db.ForeignKey('licitacao.id'), nullable=False, unique=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    condominio_id = db.Column(db.Integer, db.ForeignKey('condominio.id'), nullable=False)
    
    rating = db.Column(db.Integer, nullable=False) # Nota de 1 a 5
    comment = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    empresa = db.relationship('Empresa', backref=db.backref('avaliacoes', lazy='dynamic'))
    condominio = db.relationship('Condominio', backref=db.backref('avaliacoes', lazy='dynamic'))
