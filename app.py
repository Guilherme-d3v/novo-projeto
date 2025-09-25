import os
from pathlib import Path
from uuid import uuid4
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, session
)
from flask_mail import Mail, Message
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv

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

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if session.get("is_admin"):
            return fn(*args, **kwargs)
        return redirect(url_for("admin_login"))
    return _wrap

@app.route("/")
def index():
    try:
        condominios = Condominio.query.filter_by(status="aprovado").order_by(Condominio.created_at.desc()).limit(8).all()
    except Exception as e:
        print(f"Erro ao carregar condomínios: {e}")
        condominios = []
    
    return render_template("index.html", condominios=condominios)

@app.route("/certificar-condominio", methods=["GET", "POST"])
def certificar_condominio():
    if request.method == "POST":
        try:
            form = request.form
            pdf_file = request.files.get("pdf")
            
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
                email_verified=False
            )
            
            if pdf_file and pdf_file.filename:
                if not allowed_file(pdf_file.filename) or not pdf_file.filename.lower().endswith(".pdf"):
                    flash("Envie um PDF válido.", "warning")
                    return redirect(request.url)
                safe = secure_filename(pdf_file.filename)
                c.pdf_filename = f"{uuid4().hex}_{safe}"
                pdf_file.save(UPLOAD_DIR / c.pdf_filename)
            
            db.session.add(c)
            db.session.commit()
            
            try:
                if app.config.get("MAIL_USERNAME") and c.email:
                    token = serializer.dumps({"kind": "condominio", "id": c.id})
                    verify_url = url_for("verificar_email", token=token, _external=True)
                    msg = Message(
                        "Confirme seu e-mail - Condomínio Blindado",
                        sender=app.config["MAIL_USERNAME"],
                        recipients=[c.email]
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
                email_verified=False
            )
            
            if doc_file and doc_file.filename:
                if not allowed_file(doc_file.filename):
                    flash("Documento deve ser PDF/JPG/PNG.", "warning")
                    return redirect(request.url)
                safe = secure_filename(doc_file.filename)
                e.doc_filename = f"{uuid4().hex}_{safe}"
                doc_file.save(UPLOAD_DIR / e.doc_filename)
            
            db.session.add(e)
            db.session.commit()
            
            try:
                if app.config.get("MAIL_USERNAME") and e.email_comercial:
                    token = serializer.dumps({"kind": "empresa", "id": e.id})
                    verify_url = url_for("verificar_email", token=token, _external=True)
                    msg = Message(
                        "Confirme seu e-mail - Verificação de Empresa",
                        sender=app.config["MAIL_USERNAME"],
                        recipients=[e.email_comercial]
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

@app.route("/entrar", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        if email == app.config.get("ADMIN_EMAIL") and senha == app.config.get("ADMIN_PASSWORD"):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Credenciais inválidas.", "danger")
    return render_template("admin_login.html")

@app.route("/sair")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
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

@app.route("/admin/condominio/<int:_id>")
@admin_required
def admin_condominio_detalhe(_id):
    try:
        condominio = Condominio.query.get_or_404(_id)
    except Exception as e:
        flash(f"Condomínio não encontrado: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_condominio_detalhe.html", c=condominio)

@app.route("/admin/empresa/<int:_id>")
@admin_required
def admin_empresa_detalhe(_id):
    try:
        empresa = Empresa.query.get_or_404(_id)
    except Exception as e:
        flash(f"Empresa não encontrada: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_empresa_detalhe.html", e=empresa)

@app.route("/admin/condominios")
@admin_required
def admin_lista_condominios():
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
@admin_required
def admin_lista_empresas():
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

@app.post("/admin/condominio/<int:_id>/<string:acao>")
@admin_required
def admin_condominio_action(_id, acao):
    try:
        c = Condominio.query.get_or_404(_id)
        if acao == "aprovar":
            c.status = "aprovado"
        elif acao == "rejeitar":
            c.status = "rejeitado"
        db.session.commit()
    except Exception as e:
        flash(f"Erro ao processar ação: {str(e)}", "danger")
    
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/empresa/<int:_id>/<string:acao>")
@admin_required
def admin_empresa_action(_id, acao):
    try:
        e = Empresa.query.get_or_404(_id)
        if acao == "aprovar":
            e.status = "aprovado"
        elif acao == "rejeitar":
            e.status = "rejeitado"
        db.session.commit()
    except Exception as e:
        flash(f"Erro ao processar ação: {str(e)}", "danger")
    
    return redirect(url_for("admin_dashboard"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Adicionar tratamento de erro para debug
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

if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
