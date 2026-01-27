import os
from pathlib import Path
from uuid import uuid4
from functools import wraps
import secrets
import string
import logging
import sys # Import sys for logging to stderr

# Configura o logger para Flask
# Isso garante que as mensagens de log (INFO, WARNING, ERROR) sejam exibidas
# e capturadas pelo systemd/Gunicorn.
logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
# ... (rest of the imports)
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, session
)
from flask_mail import Mail, Message
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv

# 🌟 NOVO IMPORT DO STRIPE 🌟

import mercadopago # 🌟 IMPORT DO MERCADO PAGO 🌟
# -----------------------------

# Dependências LOCAIS que você precisa garantir que existam
from models import db, Condominio, Empresa, CondominioRank, Licitacao, Candidatura, TransacaoCoin
from config import Config

# Carregar variáveis de ambiente PRIMEIRO
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_MB = 16

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

# --- FORÇAR SERVER_NAME E PREFERRED_URL_SCHEME DIRETAMENTE NO APP ---
# Isso garante que url_for(_external=True) use o esquema e domínio corretos
# Obtidos diretamente do Config.py após o carregamento
app.config["SERVER_NAME"] = Config.SERVER_NAME
app.config["PREFERRED_URL_SCHEME"] = Config.PREFERRED_URL_SCHEME
# --- FIM DA FORÇAGEM ---

# Inicializar extensões
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])



# 🌟 INICIALIZAÇÃO DO MERCADO PAGO 🌟
# sdk = mercadopago.SDK(app.config["MP_ACCESS_TOKEN"]) # Inicializa apenas quando necessário ou globalmente
# -----------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para gerar senha temporária segura
def generate_temp_password(length=12):
    """Gera uma senha temporária complexa de 12 caracteres."""
    characters = string.ascii_letters + string.digits + string.punctuation
    temp_password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    temp_password += [secrets.choice(characters) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(temp_password)
    return ''.join(temp_password)


def login_required(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if session.get("user_type"):
            return fn(*args, **kwargs)
        return redirect(url_for("login"))
    return _wrap

# Adicione estas rotas logo após a inicialização do app e antes das outras rotas
@app.route("/blog")
def blog():
    return render_template("blog.html")

@app.route("/faq")
def faq():
    return render_template("faq.html")

@app.route("/contato", methods=["GET", "POST"])
def contato():
    if request.method == "POST":
        flash("Mensagem enviada com sucesso! Em breve entraremos em contato.", "success")
        return redirect(url_for("contato"))
    return render_template("contato.html")


@app.route("/planos")
def pricing():
    user_id = session.get("user_id")
    user_type = session.get("user_type")
    
    # Tenta buscar o condomínio se ele estiver logado para passar para o template
    condominio = None
    if user_type == "condominio" and user_id:
        condominio = Condominio.query.get(user_id)
    
    return render_template("pricing.html", c=condominio)


@app.route("/")
def index():
    try:
        condominios = Condominio.query.filter_by(status="aprovado").order_by(Condominio.created_at.desc()).limit(8).all()
    except Exception as e:
        # Se a tabela ainda não existe (no primeiro load), esta exceção evita o crash.
        print(f"Erro ao carregar condomínios: {e}") 
        condominios = []
    
    return render_template("index.html", condominios=condominios)

@app.route("/certificar-condominio", methods=["GET", "POST"])
def certificar_condominio():
    if request.method == "POST":
        try:
            form = request.form
            pdf_file = request.files.get("pdf")
            
            # A senha será gerada e enviada pelo Admin após a aprovação.
            senha_provisoria = "placeholder_pre_aprovacao"
            
            # Tratamento de erro para campos numéricos
            unidades = 0
            if form.get("unidades"):
                try:
                    unidades = int(form.get("unidades"))
                except ValueError:
                    flash("O número de unidades deve ser um valor numérico.", "danger")
                    return redirect(request.url)

            progress = 0
            if form.get("progress"):
                try:
                    progress = int(form.get("progress"))
                except ValueError:
                    flash("O progresso deve ser um valor numérico.", "danger")
                    return redirect(request.url)
            
            c = Condominio(
                nome=form.get("nome", "").strip(),
                cnpj=form.get("cnpj", "").strip(),
                tipo=form.get("tipo", "").strip(),
                unidades=unidades,
                cep=form.get("cep", "").strip(),
                endereco=form.get("endereco", "").strip(),
                cidade=form.get("cidade", "").strip(),
                estado=form.get("estado", "").strip(),
                contato_nome=form.get("contato_nome", "").strip(),
                email=form.get("email", "").strip(),
                telefone=form.get("telefone", "").strip(),
                whatsapp=form.get("whatsapp", "").strip(),
                nivel=form.get("nivel", "").strip(),
                objetivo=form.get("objetivo", "").strip(),
                observacoes=form.get("observacoes", "").strip(),
                progress=progress,
                status="pendente",
                email_verified=False,
                needs_password_change=False 
            )
            
            # Ação: Salvar a senha PROVISÓRIA.
            c.set_password(senha_provisoria)
            
            if pdf_file and pdf_file.filename:
                if not allowed_file(pdf_file.filename) or not pdf_file.filename.lower().endswith(".pdf"):
                    flash("Envie um PDF válido.", "warning")
                    return redirect(request.url)
                safe = secure_filename(pdf_file.filename)
                c.pdf_filename = f"{uuid4().hex}_{safe}"
                # pdf_file.save(UPLOAD_DIR / c.pdf_filename) 

            
            db.session.add(c)
            db.session.commit()
            
            try:
                # 🔴 ATENÇÃO: Alterado de MAIL_USERNAME para MAIL_USERNAME_SENDER (o e-mail verificado)
                if app.config.get("MAIL_USERNAME_SENDER") and c.email:
                    token = serializer.dumps({"kind": "condominio", "id": c.id})
                    verify_url = url_for("verificar_email", token=token, _external=True)
                    
                    
                    msg = Message(
                        "Confirme seu e-mail - Condomínio Blindado",
                        sender=app.config["MAIL_USERNAME_SENDER"], 
                        recipients=[c.email],
                        charset='utf-8'  
                    )
                    

                    msg.body = (
                        f"Olá {c.contato_nome or ''},\n\n"
                        f"Recebemos sua solicitação para certificar o condomínio {c.nome}.\n"
                        f"Para confirmar seu e-mail, clique no link abaixo:\n{verify_url}\n\n"
                        f"Após a verificação, a solicitação aparecerá para o time administrativo."
                    )
                    mail.send(msg)
            except Exception as e:
                print("Falha ao enviar e-mail:", e)
            
            flash("Solicitação enviada! Verifique seu e-mail para confirmar.", "success")
            return redirect(url_for("index"))
        
        except Exception as e:
            flash(f"Erro ao processar solicitação: {str(e)}", "danger")
            return redirect(request.url)
    
    return render_template("condominio_form.html")

@app.route("/cadastrar-empresa", methods=["GET", "POST"])
def cadastrar_empresa():
    if request.method == "POST":
        try:
            form = request.form
            doc_file = request.files.get("doc")
            
            # A senha será gerada e enviada pelo Admin após a aprovação.
            senha_provisoria = "placeholder_pre_aprovacao"
            
            categorias = ",".join(request.form.getlist("categorias"))
            
            e = Empresa(
                nome=form.get("nome", "").strip(),
                cnpj=form.get("cnpj", "").strip(),
                categorias=categorias,
                descricao=form.get("descricao", "").strip(),
                cidade=form.get("cidade", "").strip(),
                estado=form.get("estado", "").strip(),
                cep=form.get("cep", "").strip(),
                endereco=form.get("endereco", "").strip(),
                telefone=form.get("telefone", "").strip(),
                email_comercial=form.get("email_comercial", "").strip(),
                website=form.get("website", "").strip(),
                status="pendente",
                email_verified=False,
                needs_password_change=False
            )
            
            # Ação: Salvar a senha PROVISÓRIA.
            e.set_password(senha_provisoria)
            
            if doc_file and doc_file.filename:
                if not allowed_file(doc_file.filename):
                    flash("Documento deve ser PDF/JPG/PNG.", "warning")
                    return redirect(request.url)
                safe = secure_filename(doc_file.filename)
                e.doc_filename = f"{uuid4().hex}_{safe}"
                # doc_file.save(UPLOAD_DIR / e.doc_filename) 
            
            db.session.add(e)
            db.session.commit()
            
            try:
                # 🔴 ATENÇÃO: Alterado de MAIL_USERNAME para MAIL_USERNAME_SENDER (o e-mail verificado)
                if app.config.get("MAIL_USERNAME_SENDER") and e.email_comercial:
                    token = serializer.dumps({"kind": "empresa", "id": e.id})
                    verify_url = url_for("verificar_email", token=token, _external=True)
                    msg = Message(
                        "Confirme seu e-mail - Verificação de Empresa",
                        sender=app.config["MAIL_USERNAME_SENDER"], 
                        recipients=[e.email_comercial],
                        charset='utf-8'
                    )
                    msg.body = (
                        f"Olá, recebemos o cadastro da empresa {e.nome}.\n"
                        f"Confirme seu e-mail no link:\n{verify_url}\n\n"
                        f"Após confirmar, sua solicitação entrará para análise do time administrativo."
                    )
                    mail.send(msg)
            except Exception as e:
                print("Falha ao enviar e-mail:", e)
            
            flash("Cadastro enviado! Verifique seu e-mail para confirmar.", "success")
            return redirect(url_for("index"))
        
        except Exception as e:
            flash(f"Erro ao processar cadastro: {str(e)}", "danger")
            return redirect(request.url)
    
    return render_template("empresa_form.html")


@app.route("/verificar")
def verificar_email():
    token = request.args.get("token", "")
    try:
        data = serializer.loads(token, max_age=60 * 60 * 24 * 3)
    except SignatureExpired:
        flash("Link expirado. Envie novamente.", "warning")
        return redirect(url_for("index"))
    except BadSignature:
        flash("Link inválido.", "danger")
        return redirect(url_for("index"))
    
    kind = data.get("kind")
    _id = data.get("id")
    
    try:
        if kind == "condominio":
            c = Condominio.query.get_or_404(_id)
            c.email_verified = True
            if c.status == "pendente":
                c.status = "verificado"
            db.session.commit()
            flash("E-mail do condomínio verificado! Aguarde aprovação.", "success")
        elif kind == "empresa":
            e = Empresa.query.get_or_404(_id)
            e.email_verified = True
            if e.status == "pendente":
                e.status = "verificado"
            db.session.commit()
            flash("E-mail da empresa verificado! Aguarde aprovação.", "success")
        else:
            flash("Token desconhecido.", "danger")
    except Exception as e:
        flash(f"Erro ao verificar e-mail: {str(e)}", "danger")
    
    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        
        # 1. Tentar Login como ADMIN (SEGURANÇA IMPLEMENTADA!)
        admin_email = app.config.get("ADMIN_EMAIL")
        admin_password_hash = app.config.get("ADMIN_PASSWORD_HASH") 
        
        # Checagem SEGURA: usa o HASH do .env e a senha em texto puro do form
        if email == admin_email and check_password_hash(admin_password_hash, senha):
            session.clear()
            session["user_type"] = "admin"
            session["user_id"] = "admin"
            session["user_name"] = "Admin"
            flash("Login de Administrador efetuado.", "success")
            return redirect(url_for("admin_dashboard"))

        # 2. Tentar Login como CONDOMÍNIO
        condominio = Condominio.query.filter_by(email=email).first()
        if condominio and condominio.check_password(senha):
            if not condominio.is_active:
                flash(f"O acesso para o condomínio '{condominio.nome}' está suspenso. Contate o administrador.", "warning")
                return redirect(url_for("login"))

            session.clear()
            session["user_type"] = "condominio"
            session["user_id"] = condominio.id
            session["user_name"] = condominio.contato_nome
            flash(f"Bem-vindo(a), {condominio.contato_nome}!", "success")
            
            if condominio.needs_password_change:
                return redirect(url_for("mudar_senha"))

            return redirect(url_for("condominio_dashboard"))

        # 3. Tentar Login como EMPRESA
        empresa = Empresa.query.filter_by(email_comercial=email).first()
        if empresa and empresa.check_password(senha):
            if not empresa.is_active:
                flash(f"O acesso para a empresa '{empresa.nome}' está suspenso. Contate o administrador.", "warning")
                return redirect(url_for("login"))

            session.clear()
            session["user_type"] = "empresa"
            session["user_id"] = empresa.id
            session["user_name"] = empresa.nome
            flash(f"Bem-vindo(a), {empresa.nome}!", "success")
            
            if empresa.needs_password_change:
                return redirect(url_for("mudar_senha"))

            return redirect(url_for("empresa_dashboard"))
        
        flash("Credenciais inválidas.", "danger")
        
    return render_template("login.html") 

# NOVA ROTA: Rota forçada para troca de senha
@app.route("/mudar-senha", methods=["GET", "POST"])
@login_required
def mudar_senha():
    user_type = session.get("user_type")
    user_id = session.get("user_id")

    if user_type == "admin":
        flash("A senha do administrador deve ser alterada no arquivo .env do servidor.", "info")
        return redirect(url_for("admin_dashboard"))
        
    user_entity = None
    if user_type == "condominio":
        user_entity = Condominio.query.get(user_id)
    elif user_type == "empresa":
        user_entity = Empresa.query.get(user_id)
        
    if not user_entity:
        return redirect(url_for("logout"))
        
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirma_senha = request.form.get("confirma_senha")
        
        if nova_senha != confirma_senha:
            flash("A nova senha e a confirmação de senha não são iguais.", "danger")
            return redirect(request.url)

        if not nova_senha or len(nova_senha) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return redirect(request.url)
            
        try:
            # Salva a nova senha e reseta o flag
            user_entity.set_password(nova_senha)
            user_entity.needs_password_change = False
            db.session.commit()
            
            flash("Sua senha foi alterada com sucesso! Você está logado.", "success")
            return redirect(url_for(f"{user_type}_dashboard"))
            
        except Exception as e:
            flash(f"Erro ao salvar a nova senha: {str(e)}", "danger")
            return redirect(request.url)
            
    return render_template("mudar_senha_form.html") 


@app.route("/sair")
def logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_dashboard():
    if session.get("user_type") != "admin":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("logout"))
    
    try:
        pend_emp = Empresa.query.filter(Empresa.status.in_(["pendente", "verificado"])).count()
        pend_cond = Condominio.query.filter(Condominio.status.in_(["pendente", "verificado"])).count()
        selos = Condominio.query.count()
        
        empresas = Empresa.query.order_by(Empresa.created_at.desc()).limit(10).all()
        condominios = Condominio.query.order_by(Condominio.created_at.desc()).limit(10).all()
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        pend_emp = pend_cond = selos = 0
        empresas = condominios = []
    
    return render_template(
        "admin_dashboard.html",
        pend_emp=pend_emp, pend_cond=pend_cond, selos=selos,
        empresas=empresas, condominios=condominios
    )

@app.route("/dashboard/condominio")
@login_required
def condominio_dashboard():
    user_id = session.get("user_id")
    
    if session.get("user_type") != "condominio" or user_id == "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for("logout"))
        
    condominio = Condominio.query.get_or_404(user_id)
        
    return render_template("condominio_dashboard.html", c=condominio)


@app.route("/dashboard/condominio/licitacoes")
@login_required
def condominio_licitacoes():
    user_id = session.get("user_id")
    if session.get("user_type") != "condominio":
        flash("Acesso negado.", "danger")
        return redirect(url_for("logout"))
        
    # Busca as licitações criadas por este condomínio
    licitacoes = Licitacao.query.filter_by(condominio_id=user_id).order_by(Licitacao.created_at.desc()).all()
    
    return render_template("condominio_licitacoes.html", licitacoes=licitacoes)


@app.route("/dashboard/condominio/licitacao/<int:licitacao_id>")
@login_required
def condominio_detalhe_licitacao(licitacao_id):
    user_id = session.get("user_id")
    if session.get("user_type") != "condominio":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("logout"))

    licitacao = Licitacao.query.get_or_404(licitacao_id)

    # Garante que o condomínio só possa ver suas próprias licitações
    if licitacao.condominio_id != user_id:
        flash("Licitação não encontrada.", "danger")
        return redirect(url_for("condominio_licitacoes"))

    return render_template("condominio_detalhe_licitacao.html", licitacao=licitacao)



@app.route("/licitacoes/nova", methods=["GET", "POST"])
@login_required
def criar_licitacao():
    user_id = session.get("user_id")
    if session.get("user_type") != "condominio":
        flash("Apenas condomínios podem criar licitações.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        titulo = request.form.get("titulo")
        tipo = request.form.get("tipo_servico")
        descricao = request.form.get("descricao")
        
        if not titulo or not tipo or not descricao:
            flash("Preencha todos os campos obrigatórios.", "danger")
            return redirect(request.url)
            
        try:
            nova_licitacao = Licitacao(
                condominio_id=user_id,
                titulo=titulo,
                tipo_servico=tipo,
                descricao=descricao,
                status="aberta",
                custo_coins=10 # Valor fixo por enquanto, pode ser dinâmico no futuro
            )
            
            db.session.add(nova_licitacao)
            db.session.commit()
            
            flash("Licitação publicada com sucesso! As empresas serão notificadas.", "success")
            return redirect(url_for("condominio_dashboard"))
            
        except Exception as e:
            flash(f"Erro ao criar licitação: {str(e)}", "danger")
            return redirect(request.url)
            
    return render_template("criar_licitacao.html")

@app.route("/licitacoes")
@login_required
def listar_licitacoes():
    user_id = session.get("user_id")
    if session.get("user_type") != "empresa":
        flash("Acesso restrito a empresas.", "warning")
        return redirect(url_for("index"))
        
    empresa = Empresa.query.get(user_id)
    # Lista apenas licitações abertas
    licitacoes = Licitacao.query.filter_by(status="aberta").order_by(Licitacao.created_at.desc()).all()
    
    return render_template("lista_licitacoes.html", licitacoes=licitacoes, saldo_coins=empresa.saldo_coins)

@app.route("/licitacoes/<int:_id>")
@login_required
def detalhe_licitacao(_id):
    user_id = session.get("user_id")
    if session.get("user_type") != "empresa":
        return redirect(url_for("index"))
        
    lic = Licitacao.query.get_or_404(_id)
    empresa = Empresa.query.get(user_id)
    
    # Verifica se já se candidatou
    ja_candidatou = Candidatura.query.filter_by(licitacao_id=lic.id, empresa_id=empresa.id).first() is not None
    
    # CORREÇÃO: Trata None como 0 para evitar erro de comparação
    saldo_atual = empresa.saldo_coins if empresa.saldo_coins is not None else 0
    custo_licitacao = lic.custo_coins if lic.custo_coins is not None else 0
    saldo_insuficiente = saldo_atual < custo_licitacao
    
    return render_template("detalhe_licitacao.html", 
                           lic=lic, 
                           empresa=empresa, 
                           ja_candidatou=ja_candidatou,
                           saldo_insuficiente=saldo_insuficiente)

@app.route("/licitacoes/<int:_id>/candidatar", methods=["POST"])
@login_required
def candidatar_licitacao(_id):
    user_id = session.get("user_id")
    if session.get("user_type") != "empresa":
        return redirect(url_for("index"))
        
    lic = Licitacao.query.get_or_404(_id)
    empresa = Empresa.query.get(user_id)
    
    # Validações Finais
    if Candidatura.query.filter_by(licitacao_id=lic.id, empresa_id=empresa.id).first():
        flash("Você já se candidatou para esta vaga.", "warning")
        return redirect(url_for("detalhe_licitacao", _id=lic.id))
    
    # CORREÇÃO: Trata None como 0
    saldo_atual = empresa.saldo_coins if empresa.saldo_coins is not None else 0
    custo_licitacao = lic.custo_coins if lic.custo_coins is not None else 0

    if saldo_atual < custo_licitacao:
        flash("Saldo insuficiente.", "danger")
        return redirect(url_for("comprar_coins"))
        
    try:
        # 1. Debitar Coins
        # Se estava None, agora setamos o novo valor corretamente
        empresa.saldo_coins = saldo_atual - custo_licitacao
        
        # 2. Registrar Transação (Saída)
        transacao = TransacaoCoin(
            empresa_id=empresa.id,
            quantidade=-custo_licitacao,
            descricao=f"Candidatura Licitação #{lic.id} - {lic.titulo}",
            status="concluido"
        )
        
        # 3. Criar Candidatura
        mensagem = request.form.get("mensagem", "")
        candidatura = Candidatura(
            licitacao_id=lic.id,
            empresa_id=empresa.id,
            mensagem=mensagem,
            status="pendente"
        )
        
        db.session.add(transacao)
        db.session.add(candidatura)
        db.session.commit()
        
        # Opcional: Enviar e-mail para o condomínio notificando nova candidatura
        
        flash("Candidatura realizada com sucesso!", "success")
        return redirect(url_for("detalhe_licitacao", _id=lic.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar candidatura: {str(e)}", "danger")
        return redirect(url_for("detalhe_licitacao", _id=lic.id))

@app.route("/dashboard/empresa")
@login_required
def empresa_dashboard():
    user_id = session.get("user_id")

    if session.get("user_type") != "empresa" or user_id == "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for("logout"))
        
    empresa = Empresa.query.get_or_404(user_id)

    return render_template("empresa_dashboard.html", e=empresa)


@app.route("/dashboard/empresa/candidaturas")
@login_required
def empresa_candidaturas():
    user_id = session.get("user_id")
    if session.get("user_type") != "empresa":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("logout"))

    # Busca as candidaturas da empresa, fazendo join com a licitação para ter acesso aos detalhes
    candidaturas = db.session.query(Candidatura).join(Licitacao).filter(Candidatura.empresa_id == user_id).order_by(Licitacao.created_at.desc()).all()

    return render_template("empresa_candidaturas.html", candidaturas=candidaturas)


@app.post("/admin/condominio/<int:_id>/<string:acao>")
@login_required
def admin_condominio_action(_id, acao):
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    
    try:
        c = Condominio.query.get_or_404(_id)
        
        if acao == "aprovar":
            if not c.email_verified:
                flash("Condomínio não verificou o e-mail. Não é possível aprovar.", "warning")
                return redirect(url_for("admin_dashboard"))
            
            # Get rank from form data
            selected_rank_str = request.form.get("rank")
            
            if not selected_rank_str:
                flash("É necessário selecionar um rank para aprovar o condomínio.", "danger")
                return redirect(url_for("admin_dashboard")) # Or redirect to the detail page
            
            try:
                # Convert string to CondominioRank enum member
                selected_rank = CondominioRank[selected_rank_str.upper()] 
                c.rank = selected_rank
            except KeyError:
                flash("Rank inválido selecionado.", "danger")
                return redirect(url_for("admin_dashboard")) # Or redirect to the detail page
                
            c.status = "aprovado"
            
            # Gerar e Enviar Senha Temporária
            if not c.password_hash or c.needs_password_change == False: 
                temp_password = generate_temp_password()
                c.set_password(temp_password)
                c.needs_password_change = True 

                try:
                    msg = Message(
                        "Acesso Aprovado e Senha Temporária - Condomínio Blindado",
                        sender=app.config["MAIL_USERNAME_SENDER"], # <-- ALTERADO AQUI
                        recipients=[c.email]
                    )
                    msg.body = (
                        f"Parabéns! O condomínio {c.nome} (Rank: {c.rank.value.capitalize()}) foi aprovado.\n\n" # Added rank to email
                        f"Sua senha temporária é: {temp_password}\n"
                        f"Faça login em {url_for('login', _external=True)} para acessar e **MUDAR SUA SENHA IMEDIATAMENTE**."
                    )
                    mail.send(msg)
                    flash(f"Aprovação salva. Rank {c.rank.value.capitalize()} atribuído. Senha temporária enviada por e-mail.", "success") # Updated flash message
                except Exception as e:
                    print("Falha ao enviar e-mail de senha temporária:", e)
                    flash(f"Aprovação salva. Rank {c.rank.value.capitalize()} atribuído, mas houve falha ao enviar o e-mail. Verifique o console.", "warning") # Updated flash message

        elif acao == "rejeitar":
            c.status = "rejeitado"
            c.needs_password_change = False
            # If rejected, remove any assigned rank
            c.rank = None 
            flash("Condomínio rejeitado.", "info")
            
        db.session.commit()
    except Exception as e:
        flash(f"Erro ao processar ação: {str(e)}", "danger")
    
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/empresa/<int:_id>/<string:acao>")
@login_required
def admin_empresa_action(_id, acao):
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    
    try:
        e = Empresa.query.get_or_404(_id)
        
        if acao == "aprovar":
            if not e.email_verified:
                flash("Empresa não verificou o e-mail. Não é possível aprovar.", "warning")
                return redirect(url_for("admin_dashboard"))
                
            e.status = "aprovado"
            
            # Gerar e Enviar Senha Temporária
            if not e.password_hash or e.needs_password_change == False: 
                temp_password = generate_temp_password()
                e.set_password(temp_password)
                e.needs_password_change = True 

                try:
                    msg = Message(
                        "Acesso Aprovado e Senha Temporária - Condomínio Blindado",
                        sender=app.config["MAIL_USERNAME_SENDER"], # <-- ALTERADO AQUI
                        recipients=[e.email_comercial]
                    )
                    msg.body = (
                        f"Parabéns! A empresa {e.nome} foi aprovada.\n\n"
                        f"Sua senha temporária é: {temp_password}\n"
                        f"Faça login em {url_for('login', _external=True)} para acessar e **MUDAR SUA SENHA IMEDIATAMENTE**."
                    )
                    mail.send(msg)
                    flash("Aprovação salva. Senha temporária enviada por e-mail.", "success")
                except Exception as e:
                    print("Falha ao enviar e-mail de senha temporária:", e)
                    flash("Aprovação salva, mas houve falha ao enviar o e-mail. Verifique o console.", "warning")

        elif acao == "rejeitar":
            e.status = "rejeitado"
            e.needs_password_change = False
            flash("Empresa rejeitada.", "info")
            
        db.session.commit()
    except Exception as e:
        flash(f"Erro ao processar ação: {str(e)}", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/condominio/<int:_id>")
@login_required
def admin_condominio_detalhe(_id):
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    try:
        condominio = Condominio.query.get_or_404(_id)
    except Exception as e:
        flash(f"Condomínio não encontrado: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_condominio_detalhe.html", c=condominio)

@app.route("/admin/empresa/<int:_id>")
@login_required
def admin_empresa_detalhe(_id):
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    try:
        empresa = Empresa.query.get_or_404(_id)
    except Exception as e:
        flash(f"Empresa não encontrada: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_empresa_detalhe.html", e=empresa)


@app.post("/admin/condominio/<int:_id>/set-active")
@login_required
def admin_set_active_condominio(_id):
    if session.get("user_type") != "admin":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("logout"))

    c = Condominio.query.get_or_404(_id)
    is_active_str = request.form.get("is_active")
    
    if is_active_str is None:
        flash("Nenhuma ação selecionada.", "danger")
        return redirect(url_for("admin_condominio_detalhe", _id=_id))

    is_active = is_active_str.lower() == 'true'
    
    if c.is_active == is_active:
        flash(f"O status do condomínio já é {'ativo' if is_active else 'suspenso'}.", "info")
    else:
        c.is_active = is_active
        db.session.commit()
        flash(f"Status do condomínio atualizado para {'ativo' if is_active else 'suspenso'}.", "success")

        if not is_active:
            try:
                msg = Message(
                    "Sua conta foi temporariamente suspensa - Condomínio Blindado",
                    sender=app.config["MAIL_USERNAME_SENDER"],
                    recipients=[c.email]
                )
                msg.body = (
                    f"Olá {c.contato_nome},\n\n"
                    f"Sua conta para o condomínio {c.nome} foi temporariamente suspensa por um administrador.\n"
                    "Estamos investigando o caso. Se você acredita que isso é um engano ou precisa de mais informações, "
                    "por favor, entre em contato conosco pelo e-mail: administrador@condblindado.com.br\n\n"
                    "Atenciosamente,\nEquipe Condomínio Blindado"
                )
                mail.send(msg)
                flash("E-mail de notificação de suspensão enviado ao usuário.", "info")
            except Exception as e:
                print(f"Falha ao enviar e-mail de suspensão: {e}")
                flash("Houve uma falha ao enviar o e-mail de notificação de suspensão. Verifique o console.", "warning")
        else:
            try:
                msg = Message(
                    "Sua conta foi reativada - Condomínio Blindado",
                    sender=app.config["MAIL_USERNAME_SENDER"],
                    recipients=[c.email]
                )
                msg.body = (
                    f"Olá {c.contato_nome},\n\n"
                    f"Boas notícias! Sua conta para o condomínio {c.nome} foi reativada.\n"
                    "Você já pode acessar o sistema normalmente.\n\n"
                    "Atenciosamente,\nEquipe Condomínio Blindado"
                )
                mail.send(msg)
                flash("E-mail de notificação de reativação enviado ao usuário.", "info")
            except Exception as e:
                print(f"Falha ao enviar e-mail de reativação: {e}")
                flash("Houve uma falha ao enviar o e-mail de notificação de reativação. Verifique o console.", "warning")

    return redirect(url_for("admin_condominio_detalhe", _id=_id))

@app.post("/admin/empresa/<int:_id>/set-active")
@login_required
def admin_set_active_empresa(_id):
    if session.get("user_type") != "admin":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("logout"))

    e = Empresa.query.get_or_404(_id)
    is_active_str = request.form.get("is_active")

    if is_active_str is None:
        flash("Nenhuma ação selecionada.", "danger")
        return redirect(url_for("admin_empresa_detalhe", _id=_id))

    is_active = is_active_str.lower() == 'true'
    
    if e.is_active == is_active:
        flash(f"O status da empresa já é {'ativo' if is_active else 'suspenso'}.", "info")
    else:
        e.is_active = is_active
        db.session.commit()
        flash(f"Status da empresa atualizado para {'ativo' if is_active else 'suspenso'}.", "success")

        if not is_active:
            try:
                msg = Message(
                    "Sua conta foi temporariamente suspensa - Condomínio Blindado",
                    sender=app.config["MAIL_USERNAME_SENDER"],
                    recipients=[e.email_comercial]
                )
                msg.body = (
                    f"Olá {e.nome},\n\n"
                    f"Sua conta de empresa foi temporariamente suspensa por um administrador.\n"
                    "Estamos investigando o caso. Se você acredita que isso é um engano ou precisa de mais informações, "
                    "por favor, entre em contato conosco pelo e-mail: administrador@condblindado.com.br\n\n"
                    "Atenciosamente,\nEquipe Condomínio Blindado"
                )
                mail.send(msg)
                flash("E-mail de notificação de suspensão enviado ao usuário.", "info")
            except Exception as ex:
                print(f"Falha ao enviar e-mail de suspensão: {ex}")
                flash("Houve uma falha ao enviar o e-mail de notificação de suspensão. Verifique o console.", "warning")
        else:
            try:
                msg = Message(
                    "Sua conta foi reativada - Condomínio Blindado",
                    sender=app.config["MAIL_USERNAME_SENDER"],
                    recipients=[e.email_comercial]
                )
                msg.body = (
                    f"Olá {e.nome},\n\n"
                    f"Boas notícias! Sua conta de empresa foi reativada.\n"
                    "Você já pode acessar o sistema normalmente.\n\n"
                    "Atenciosamente,\nEquipe Condomínio Blindado"
                )
                mail.send(msg)
                flash("E-mail de notificação de reativação enviado ao usuário.", "info")
            except Exception as ex:
                print(f"Falha ao enviar e-mail de reativação: {ex}")
                flash("Houve uma falha ao enviar o e-mail de notificação de reativação. Verifique o console.", "warning")
    
    return redirect(url_for("admin_empresa_detalhe", _id=_id))

@app.route("/admin/condominios")
@login_required
def admin_lista_condominios():
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    status_filter = request.args.get("status", "pendente")
    
    query = Condominio.query.order_by(Condominio.created_at.desc())
    
    if status_filter == "pendente":
        condominios = query.filter(Condominio.status.in_(["pendente", "verificado"])).all()
    elif status_filter == "aprovado":
        condominios = query.filter(Condominio.status == "aprovado").all()
    elif status_filter == "rejeitado":
        condominios = query.filter(Condominio.status == "rejeitado").all()
    else:
        condominios = query.all()
        
    return render_template("admin_lista.html",
                           itens=condominios,
                           tipo="condominio",
                           titulo="Condomínios",
                           status_filter=status_filter)

@app.route("/admin/empresas")
@login_required
def admin_lista_empresas():
    if session.get("user_type") != "admin": return redirect(url_for("logout"))
    status_filter = request.args.get("status", "pendente")
    
    query = Empresa.query.order_by(Empresa.created_at.desc())
    
    if status_filter == "pendente":
        empresas = query.filter(Empresa.status.in_(["pendente", "verificado"])).all()
    elif status_filter == "aprovado":
        empresas = query.filter(Empresa.status == "aprovado").all()
    elif status_filter == "rejeitado":
        empresas = query.filter(Empresa.status == "rejeitado").all()
    else:
        empresas = query.all()
        
    return render_template("admin_lista.html",
                           itens=empresas,
                           tipo="empresa",
                           titulo="Empresas Parceiras",
                           status_filter=status_filter)

@app.route("/condominios-certificados")
def lista_certificados():
    try:
        condominios = Condominio.query.filter_by(status="aprovado").order_by(Condominio.nome).all()
    except Exception as e:
        print(f"Erro ao listar certificados: {e}")
        condominios = []
        
    return render_template("certificados.html", condominios=condominios)

@app.route("/empresas-parceiras")
def lista_empresas():
    try:
        empresas = Empresa.query.filter_by(status="aprovado").order_by(Empresa.nome).all()
    except Exception as e:
        print(f"Erro ao listar empresas: {e}")
        empresas = []
        
    return render_template("empresas_parceiras.html", empresas=empresas)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # ATENÇÃO: Esta rota só funcionará se você configurar um CDN ou armazenamento persistente.
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Erro interno não tratado: {error}", exc_info=True)
    return "Ocorreu um erro interno no servidor.", 500

def create_tables():
    """Criar tabelas manualmente"""
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {e}")

# ------------------------------------------------------------------------
# 🌟 NOVAS ROTAS MERCADO PAGO (COINS) 🌟
# ------------------------------------------------------------------------

@app.route("/comprar-coins")
@login_required
def comprar_coins():
    if session.get("user_type") != "empresa":
        flash("Apenas empresas podem comprar coins.", "warning")
        return redirect(url_for("index"))
    
    return render_template("comprar_coins.html")

@app.route("/mp/criar-pagamento", methods=["POST"])
@login_required
def mp_criar_pagamento():
    user_id = session.get("user_id")
    if session.get("user_type") != "empresa":
        return {"error": "Acesso não autorizado"}, 401

    # --- CORREÇÃO DE ROBUSTEZ ---
    # Busca a empresa no início e verifica se ela existe
    empresa = Empresa.query.get(user_id)
    if not empresa:
        app.logger.error(f"Tentativa de criar pagamento para empresa inexistente com user_id: {user_id}")
        return {"error": "Empresa não encontrada"}, 404
    # --- FIM DA CORREÇÃO ---

    try:
        data = request.json
        pacote_id = data.get("pacote_id")

        pacotes = {
            "pacote_1": {"qtd": 50, "preco": 50.00, "titulo": "50 Coins"},
            "pacote_2": {"qtd": 120, "preco": 100.00, "titulo": "120 Coins (Bônus)"},
            "pacote_3": {"qtd": 300, "preco": 200.00, "titulo": "300 Coins (Mega Bônus)"}
        }

        pacote = pacotes.get(pacote_id)
        if not pacote:
            return {"error": "Pacote inválido"}, 400

        sdk = mercadopago.SDK(app.config["MP_ACCESS_TOKEN"])

        # Cria a preferência de pagamento com todos os dados necessários
        preference_data = {
            "items": [
                {
                    "title": f"Pacote de Coins - {pacote['titulo']}",
                    "quantity": 1,
                    "unit_price": pacote["preco"]
                }
            ],
            "payer": {
                "email": empresa.email_comercial,  # USA A EMPRESA JÁ VERIFICADA
            },
            "back_urls": {
                "success": f"{Config.BASE_URL}/mp/success",
                "failure": f"{Config.BASE_URL}/mp/failure",
                "pending": f"{Config.BASE_URL}/mp/pending",
            },
            "auto_return": "approved",
            "notification_url": f"{Config.BASE_URL}/mp/webhook",
            "metadata": {
                "empresa_id": user_id,
                "coins_qtd": pacote['qtd']
            }
        }

        preference_response = sdk.preference().create(preference_data)

        if preference_response.get("status") in [200, 201]:
            preference = preference_response["response"]
            return {"init_point": preference["init_point"], "preference_id": preference["id"]}, 200
        else:
            app.logger.error(f"Erro MP ao criar preferência: {preference_response}")
            return {"error": "Falha ao criar preferência de pagamento."}, 500

    except Exception as e:
        app.logger.error(f"Erro inesperado em mp_criar_pagamento: {e}", exc_info=True)
        return {"error": str(e)}, 500

@app.route("/mp/success")
def mp_success():
    flash("Pagamento processado! Seus coins serão creditados assim que o Mercado Pago confirmar.", "success")
    return redirect(url_for("empresa_dashboard"))

@app.route("/mp/failure")
def mp_failure():
    flash("Pagamento falhou ou foi cancelado.", "danger")
    return redirect(url_for("comprar_coins"))

@app.route("/mp/pending")
def mp_pending():
    flash("Pagamento em análise.", "info")
    return redirect(url_for("empresa_dashboard"))

@app.route("/mp/webhook", methods=["POST"])
def mp_webhook():
    app.logger.info("-> mp_webhook function entered.")
    data = request.json if request.is_json else request.form.to_dict()
    app.logger.warning(f"Webhook MP recebido: {data}")

    try:
        # Verifica o tipo de notificação
        topic = data.get('topic')
        
        if topic == 'payment':
            # Tenta extrair o payment_id de diferentes estruturas de webhook
            payment_id = data.get('data', {}).get('id')
            if not payment_id: # Se não encontrou no 'data.id', tenta no 'resource'
                payment_id = data.get('resource')
                if payment_id and "http" in payment_id: # Se for uma URL, extrai o ID do final
                    try:
                        payment_id = payment_id.split('/')[-1]
                    except Exception:
                        payment_id = None
            
            if not payment_id:
                app.logger.info("Webhook de pagamento ignorado (não contém ID de pagamento válido).")
                return "Notification ignored", 200

            app.logger.info(f"Processando pagamento ID: {payment_id}")
            app.logger.info(f"Inicializando SDK do Mercado Pago com token: {app.config['MP_ACCESS_TOKEN']}")
            sdk = mercadopago.SDK(app.config["MP_ACCESS_TOKEN"])
            app.logger.info(f"Consultando detalhes do pagamento {payment_id} no MP.")
            payment_info_response = sdk.payment().get(payment_id)
            app.logger.info(f"Resposta da consulta de pagamento: {payment_info_response}")
            
            if not payment_info_response or payment_info_response.get("status") != 200:
                app.logger.error(f"Erro ao consultar o pagamento {payment_id} na API do MP. Resposta: {payment_info_response}")
                return "Failed to get payment info", 500

            payment = payment_info_response["response"]
            status = payment.get("status")
            metadata = payment.get("metadata", {})
            empresa_id = metadata.get("empresa_id") 
            coins_qtd = metadata.get("coins_qtd")
            
            # NOVO: Lógica para processar compra de planos (Condomínio)
            condominio_id = metadata.get("condominio_id")
            plano_assinatura = metadata.get("plano_assinatura")

            if status == "approved":
                if empresa_id and coins_qtd: # Processamento de coins para Empresas
                    existe = TransacaoCoin.query.filter_by(payment_id=str(payment_id)).first()
                    if existe:
                        app.logger.warning(f"Pagamento ID {payment_id} (coins) já processado anteriormente.")
                        return "OK", 200

                    empresa = Empresa.query.get(empresa_id)
                    if empresa:
                        saldo_atual = empresa.saldo_coins if empresa.saldo_coins is not None else 0
                        empresa.saldo_coins = saldo_atual + int(coins_qtd)
                        
                        transacao = TransacaoCoin(
                            empresa_id=empresa.id,
                            quantidade=int(coins_qtd),
                            descricao=f"Compra de {coins_qtd} coins via Mercado Pago",
                            payment_id=str(payment_id),
                            status="concluido"
                        )
                        db.session.add(transacao)
                        db.session.add(empresa)
                        db.session.commit()
                        app.logger.info(f"💰 SUCESSO: {coins_qtd} Coins creditados para Empresa ID {empresa_id}")
                    else:
                        app.logger.error(f"Empresa ID {empresa_id} não encontrada para pagamento {payment_id}.")
                
                elif condominio_id and plano_assinatura: # Processamento de planos para Condomínios
                    # Verifica se o pagamento já foi processado para evitar duplicidade
                    # Podemos usar a TransacaoCoin para planos também, ou criar uma nova tabela para Assinaturas
                    # Por simplicidade, vamos usar aqui como se fosse uma transação de "compra de plano"
                    existe_transacao = TransacaoCoin.query.filter_by(payment_id=str(payment_id), empresa_id=None, condominio_id=condominio_id).first()
                    if existe_transacao:
                        app.logger.warning(f"Pagamento ID {payment_id} (plano) já processado anteriormente.")
                        return "OK", 200

                    condominio = Condominio.query.get(condominio_id)
                    if condominio:
                        from datetime import datetime, timedelta
                        condominio.plano_assinatura = plano_assinatura
                        # Define a expiração para um mês a partir de agora
                        condominio.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
                        
                        # Registra a transação do plano
                        transacao_plano = TransacaoCoin( # Reutilizando TransacaoCoin para o plano
                            condominio_id=condominio.id,
                            quantidade=int(payment.get("transaction_amount", 0)), # Salva o valor da compra
                            descricao=f"Compra do plano {plano_assinatura} via Mercado Pago",
                            payment_id=str(payment_id),
                            status="concluido"
                        )
                        db.session.add(transacao_plano)
                        db.session.add(condominio)
                        db.session.commit()
                        app.logger.info(f"✅ SUCESSO: Plano {plano_assinatura} ativado para Condomínio ID {condominio_id}")
                    else:
                        app.logger.error(f"Condomínio ID {condominio_id} não encontrado para pagamento do plano {payment_id}.")
                else:
                    app.logger.warning(f"Pagamento ID {payment_id} aprovado, mas sem empresa_id/coins_qtd ou condominio_id/plano_assinatura nos metadados.")
            else:
                app.logger.warning(f"Pagamento ID {payment_id} não processado. Status: {status}")
            
                        
            
                        # Garante que sempre haja um retorno para o tópico 'payment'
            
        return "OK", 200 
            
                    
            
                    # Se o tópico não for 'payment', ainda precisamos retornar algo.
            
                    # Por exemplo, para merchant_order, ou outros tópicos que o MP possa enviar.
            
        return "OK", 200 # <--- Adicionado retorno padrão aqui
            
                    
            
    except Exception as e:
        app.logger.error(f"❌ Erro fatal no Webhook MP: {e}", exc_info=True)
        return "Internal Server Error", 500

@app.route("/mp/criar-assinatura-recorrente", methods=["POST"])
@login_required
def mp_criar_assinatura_recorrente():
    condominio_id = session.get("user_id")
    if session.get("user_type") != "condominio":
        return {"error": "Acesso não autorizado"}, 401

    condominio = Condominio.query.get(condominio_id)
    if not condominio:
        app.logger.error(f"Tentativa de criar assinatura para condomínio inexistente com user_id: {condominio_id}")
        return {"error": "Condomínio não encontrado"}, 404

    try:
        data = request.json
        plano_id_str = data.get("plano_id")

        # Mapeamento dos planos internos para IDs de preapproval_plan do Mercado Pago
        # VOCÊ PRECISA CRIAR ESTES PLANOS NO SEU PAINEL DO MERCADO PAGO E COLOCAR OS IDs REAIS AQUI
        planos_mp = {
            "plano_basico": {
                "title": "Plano Básico Condomínio Blindado",
                "description": "Certificação Bronze, Suporte Básico, 1 Licitação/mês",
                "price": 99.00,
                "frequency": 1, # Mensal
                "frequency_type": "months",
                # "preapproval_plan_id": app.config["MP_PLAN_ID_BASIC"] # Removido
            },
            "plano_avancado": {
                "title": "Plano Avançado Condomínio Blindado",
                "description": "Certificação Prata, Suporte Prioritário, 3 Licitações/mês, Relatórios Mensais",
                "price": 199.00,
                "frequency": 1, # Mensal
                "frequency_type": "months",
                # "preapproval_plan_id": app.config["MP_PLAN_ID_ADVANCED"] # Removido
            },
            "plano_premium": {
                "title": "Plano Premium Condomínio Blindado",
                "description": "Certificação Ouro, Suporte VIP 24/7, Licitações Ilimitadas, Relatórios Personalizados, Consultoria",
                "price": 299.00,
                "frequency": 1, # Mensal
                "frequency_type": "months",
                # "preapproval_plan_id": app.config["MP_PLAN_ID_PREMIUM"] # Removido
            }
        }

        plano_escolhido = planos_mp.get(plano_id_str)
        if not plano_escolhido:
            return {"error": "Plano inválido"}, 400
        
        # Validar se o preapproval_plan_id foi configurado


        sdk = mercadopago.SDK(app.config["MP_ACCESS_TOKEN"])

        # Cria a preferência de pagamento (agora como um pagamento único)
        preference_data = {
            "items": [
                {
                    "title": plano_escolhido["title"],
                    "description": plano_escolhido["description"],
                    "quantity": 1,
                    "unit_price": plano_escolhido["price"],
                    "currency_id": "BRL"
                }
            ],
            "payer": {
                "email": condominio.email,
            },
            "back_urls": {
                "success": f"{Config.BASE_URL}/mp/assinatura-status?status=approved",
                "failure": f"{Config.BASE_URL}/mp/assinatura-status?status=rejected",
                "pending": f"{Config.BASE_URL}/mp/assinatura-status?status=pending",
            },
            "auto_return": "approved",
            "notification_url": f"{Config.BASE_URL}/mp/webhook",
            "metadata": {
                "condominio_id": condominio.id,
                "plano_assinatura": plano_id_str
            }
        }

        preference_response = sdk.preference().create(preference_data)

        if preference_response.get("status") in [200, 201]:
            preference = preference_response["response"]
            # Salva o plano no condomínio (status inicial)
            condominio.plano_assinatura = plano_id_str
            # subscription_expires_at será atualizado pelo webhook após o pagamento
            db.session.commit()

            return {"init_point": preference["init_point"], "preference_id": preference["id"]}, 200
        else:
            app.logger.error(f"Erro MP ao criar pré-aprovação: {preapproval_response}")
            return {"error": "Falha ao criar assinatura. Tente novamente mais tarde."}, 500

    except Exception as e:
        app.logger.error(f"Erro inesperado em mp_criar_assinatura_recorrente: {e}", exc_info=True)
        return {"error": str(e)}, 500

@app.route("/mp/assinatura-status")
@login_required
def mp_assinatura_status():
    # Rota de retorno após o usuário interagir com o Mercado Pago
    status = request.args.get("status")
    preapproval_id = request.args.get("preapproval_id")

    if status == "approved":
        flash("Sua assinatura foi criada com sucesso! Aguarde a confirmação do primeiro pagamento.", "success")
    elif status == "pending":
        flash("Sua assinatura está pendente de aprovação do Mercado Pago.", "info")
    elif status == "in_process":
        flash("O pagamento da sua assinatura está em análise.", "info")
    else: # canceled, rejected, etc.
        flash("Não foi possível processar sua assinatura. Tente novamente.", "danger")
    
    # O webhook cuidará da atualização final do banco de dados
    return redirect(url_for("condominio_dashboard"))

# ------------------------------------------------------------------------
# FIM DAS NOVAS ROTAS MERCADO PAGO (ASSINATURAS) 
# ------------------------------------------------------------------------



@app.context_processor
def inject_user():
    return dict(session)

if __name__ == "__main__":
    app.run(debug=True)

