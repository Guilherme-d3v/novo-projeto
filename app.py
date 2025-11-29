import os
from pathlib import Path
from uuid import uuid4
from functools import wraps
import secrets
import string

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
import stripe
# -----------------------------

# Dependências LOCAIS que você precisa garantir que existam
from models import db, Condominio, Empresa
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

# Inicializar extensões
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# 🌟 INICIALIZAÇÃO DO STRIPE 🌟
# Configura a chave secreta globalmente para a API
stripe.api_key = app.config["STRIPE_SECRET_KEY"]
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
            flash("Login de Administrador efetuado.", "success")
            return redirect(url_for("admin_dashboard"))

        # 2. Tentar Login como CONDOMÍNIO
        condominio = Condominio.query.filter_by(email=email).first()
        if condominio and condominio.check_password(senha):
            session.clear()
            session["user_type"] = "condominio"
            session["user_id"] = condominio.id
            flash(f"Bem-vindo(a), {condominio.contato_nome}!", "success")
            
            # NOVO: Verificar se precisa mudar a senha
            if condominio.needs_password_change:
                flash("Por favor, defina uma nova senha para sua conta por segurança.", "info")
                return redirect(url_for("mudar_senha"))

            return redirect(url_for("condominio_dashboard"))

        # 3. Tentar Login como EMPRESA
        empresa = Empresa.query.filter_by(email_comercial=email).first()
        if empresa and empresa.check_password(senha):
            session.clear()
            session["user_type"] = "empresa"
            session["user_id"] = empresa.id
            flash(f"Bem-vindo(a), {empresa.nome}!", "success")
            
            # NOVO: Verificar se precisa mudar a senha
            if empresa.needs_password_change:
                flash("Por favor, defina uma nova senha para sua conta por segurança.", "info")
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
    
    # Admins nao precisam trocar senha aqui
    if user_type == "admin":
        flash("Administradores não precisam usar este recurso.", "warning")
        return redirect(url_for("admin_dashboard"))
        
    user_entity = None
    if user_type == "condominio":
        user_entity = Condominio.query.get(user_id)
    elif user_type == "empresa":
        user_entity = Empresa.query.get(user_id)
        
    if not user_entity:
        return redirect(url_for("logout"))
        
    # Se o flag for False e ele tentar acessar a rota, o redireciona
    if not user_entity.needs_password_change:
        flash("Sua senha já está segura.", "success")
        return redirect(url_for(f"{user_type}_dashboard"))
    
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
            
    # GET request
    return render_template("mudar_senha.html") 


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
    
    if condominio.needs_password_change:
        return redirect(url_for("mudar_senha"))
        
    return render_template("condominio_dashboard.html", c=condominio)

@app.route("/dashboard/empresa")
@login_required
def empresa_dashboard():
    user_id = session.get("user_id")

    if session.get("user_type") != "empresa" or user_id == "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for("logout"))
        
    empresa = Empresa.query.get_or_404(user_id)
    
    if empresa.needs_password_change:
        return redirect(url_for("mudar_senha"))

    return render_template("empresa_dashboard.html", e=empresa)


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
                        f"Parabéns! O condomínio {c.nome} foi aprovado.\n\n"
                        f"Sua senha temporária é: {temp_password}\n"
                        f"Faça login em {url_for('login', _external=True)} para acessar e **MUDAR SUA SENHA IMEDIATAMENTE**."
                    )
                    mail.send(msg)
                    flash("Aprovação salva. Senha temporária enviada por e-mail.", "success")
                except Exception as e:
                    print("Falha ao enviar e-mail de senha temporária:", e)
                    flash("Aprovação salva, mas houve falha ao enviar o e-mail. Verifique o console.", "warning")

        elif acao == "rejeitar":
            c.status = "rejeitado"
            c.needs_password_change = False
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
    return f"Erro interno: {error}", 500

def create_tables():
    """Criar tabelas manualmente"""
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {e}")

# ------------------------------------------------------------------------
# 🌟 NOVAS ROTAS STRIPE 🌟
# ------------------------------------------------------------------------

@app.route("/create-checkout-session/<int:_id>", methods=["POST"])
@login_required
def create_checkout_session(_id):
    user_type = session.get("user_type")
    
    # Validação de segurança: o usuário logado deve ser o proprietário do ID
    if user_type != "condominio" or session.get("user_id") != _id:
        flash("Ação não permitida.", "danger")
        return redirect(url_for("logout"))
    
    condominio = Condominio.query.get_or_404(_id)
    
    try:
        # 1. Cria ou recupera o Customer ID do Stripe
        if not condominio.stripe_customer_id:
            customer = stripe.Customer.create(
                email=condominio.email,
                name=condominio.nome,
                metadata={'condominio_id': condominio.id}
            )
            condominio.stripe_customer_id = customer.id
            db.session.commit()
        
        # 2. Cria a Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=condominio.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": app.config["STRIPE_PRICE_ID_MONTHLY"],
                    "quantity": 1,
                },
            ],
            mode="subscription",
            # Redirecionamento após sucesso/cancelamento
            success_url=url_for("success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("cancel", _external=True),
        )
        
        # Redireciona o usuário para a página de pagamento do Stripe
        return redirect(checkout_session.url, code=303)
        
    except stripe.error.StripeError as e:
        # Erros específicos do Stripe (ex: chave inválida, preço não existe)
        flash(f"Erro ao criar sessão de checkout: {str(e)}", "danger")
        return redirect(url_for("condominio_dashboard"))
    except Exception as e:
        # Outros erros de sistema/banco de dados
        flash(f"Ocorreu um erro inesperado: {str(e)}", "danger")
        return redirect(url_for("condominio_dashboard"))


@app.route("/success")
@login_required # Garante que apenas um usuário logado acesse
def success():
    # Nota: O status final do pagamento é definido pelo Webhook, não por esta rota.
    flash("Assinatura iniciada com sucesso! Verifique seu dashboard para o status final.", "success")
    return redirect(url_for("condominio_dashboard"))

@app.route("/cancel")
@login_required # Garante que apenas um usuário logado acesse
def cancel():
    flash("Pagamento cancelado.", "info")
    return redirect(url_for("condominio_dashboard"))

# 🌟 ROTA CRÍTICA: WEBHOOK 🌟
@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    event = None
    
    try:
        # Verifica se o evento é genuíno do Stripe usando a chave secreta do webhook
        event = stripe.Webhook.construct_event(
            payload, sig_header, app.config["STRIPE_WEBHOOK_SECRET"]
        )
    except ValueError as e:
        # Payload inválido
        print(f"Erro do Webhook: Payload inválido: {e}")
        return "Payload inválido", 400
    except stripe.error.SignatureVerificationError as e:
        # Assinatura inválida
        print(f"Erro do Webhook: Assinatura inválida: {e}")
        return "Assinatura inválida", 400

    # ------------------------------------
    # Processamento dos Tipos de Eventos
    # ------------------------------------
    
    if event["type"] == "checkout.session.completed":
        # O cliente concluiu a compra.
        session_data = event["data"]["object"]
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")
        
        condominio = Condominio.query.filter_by(stripe_customer_id=customer_id).first()
        
        if condominio and subscription_id:
            condominio.stripe_subscription_id = subscription_id
            # Definimos como 'active' se o pagamento for imediato, ou 'trialing'
            # Se for um trial, os próximos webhooks ajustarão o status.
            condominio.subscription_status = "active" 
            db.session.commit()
            print(f"✅ Assinatura criada para Condomínio ID {condominio.id}")
            
    elif event["type"] in ["customer.subscription.updated", "customer.subscription.deleted"]:
        # Mudança no status da assinatura (cancelada, expirada, etc.)
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        
        condominio = Condominio.query.filter_by(stripe_customer_id=customer_id).first()

        if condominio:
            condominio.subscription_status = subscription.get("status")
            db.session.commit()
            print(f"⚠️ Status da Assinatura atualizado para Condomínio ID {condominio.id}: {condominio.subscription_status}")

    elif event["type"] == "invoice.payment_succeeded":
        # O Stripe confirmou que um pagamento recorrente foi processado com sucesso
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        
        condominio = Condominio.query.filter_by(stripe_customer_id=customer_id).first()
        
        if condominio:
            # Garante que o status esteja como ativo após um pagamento mensal
            condominio.subscription_status = "active"
            db.session.commit()
            print(f"💰 Pagamento recorrente bem-sucedido para Condomínio ID {condominio.id}")

    # Retorne um response para o Stripe para confirmar o recebimento
    return "", 200

# ------------------------------------------------------------------------
# FIM DAS NOVAS ROTAS STRIPE 
# ------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)