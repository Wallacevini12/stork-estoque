"""
Stork Estoque — app.py
Sistema de estoque com rastreabilidade por código de barras
Stack: Flask + MySQL + PWA
Deploy: Railway.app
"""

import os
import io
import json
import barcode
import requests
from barcode.writer import ImageWriter
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, send_file, abort
)
from flask_mysqldb import MySQL
from reportlab.lib.pagesizes import mm
from reportlab.lib.units import mm as reportlab_mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader

# ── App ────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "stork-estoque-dev-key")

# ── MySQL (Railway injeta as vars automaticamente) ─────────────
app.config["MYSQL_HOST"]     = os.getenv("DB_HOST", "localhost")
app.config["MYSQL_PORT"]     = int(os.getenv("DB_PORT", 3306))
app.config["MYSQL_DB"]       = os.getenv("DB_NAME", "estoque")
app.config["MYSQL_USER"]     = os.getenv("DB_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("DB_PASS", "")
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL(app)

# ── Config externa: URL da API do Stork ERP ────────────────────
STORK_API_URL = os.getenv("STORK_ERP_URL", "https://erpstork-production.up.railway.app")
STORK_API_KEY = os.getenv("STORK_API_KEY", "")


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def login_required(f):
    """Decorator: redireciona para login se não autenticado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def stork_api_get(endpoint: str) -> dict | None:
    """Consulta a API REST do Stork ERP com timeout e tratamento de erro."""
    try:
        r = requests.get(
            f"{STORK_API_URL}{endpoint}",
            headers={"X-API-Key": STORK_API_KEY},
            timeout=8
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def gerar_barcode_png(codigo: str) -> bytes:
    """Gera PNG do Code128 em memória e retorna os bytes."""
    CODE128 = barcode.get_barcode_class("code128")
    buf = io.BytesIO()
    CODE128(codigo, writer=ImageWriter()).write(buf, options={
        "module_width": 0.4,
        "module_height": 8.0,
        "font_size": 7,
        "text_distance": 2.0,
        "quiet_zone": 2.0,
        "write_text": True,
    })
    buf.seek(0)
    return buf.read()


def gerar_etiqueta_pdf(item: dict) -> bytes:
    """
    Gera PDF de etiqueta 100x50mm pronto para Elgin L42 Pro.

    Campos impressos:
      - Código de barras Code128 (codigo_peca)
      - Nome / descrição da peça
      - Cliente
      - Quantidade em estoque
      - Local de armazenagem
      - Observação (opcional)
    """
    W, H = 100 * reportlab_mm, 50 * reportlab_mm

    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(W, H))

    # ── Barcode ────────────────────────────────────────────────
    barcode_png = gerar_barcode_png(item["codigo_peca"])
    barcode_img = ImageReader(io.BytesIO(barcode_png))
    c.drawImage(barcode_img, 4 * reportlab_mm, 22 * reportlab_mm,
                width=92 * reportlab_mm, height=22 * reportlab_mm,
                preserveAspectRatio=True, anchor="sw")

    # ── Textos ─────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    nome = item.get("nome_peca", "")[:52]
    c.drawString(4 * reportlab_mm, 18 * reportlab_mm, nome)

    c.setFont("Helvetica", 7)
    cliente = f"Cliente: {item.get('cliente', '')}"
    c.drawString(4 * reportlab_mm, 13 * reportlab_mm, cliente)

    qtd_local = f"Qtd: {item.get('quantidade', 0)}  |  Local: {item.get('local', '-')}"
    c.drawString(4 * reportlab_mm, 9 * reportlab_mm, qtd_local)

    obs = item.get("observacao", "")
    if obs:
        c.setFont("Helvetica-Oblique", 6)
        c.drawString(4 * reportlab_mm, 5 * reportlab_mm, obs[:80])

    c.save()
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha   = request.form.get("senha", "")

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, nome FROM usuario WHERE usuario = %s AND senha = MD5(%s) AND ativo = 1",
            (usuario, senha)
        )
        user = cur.fetchone()
        cur.close()

        if user:
            session["usuario_id"]   = user["id"]
            session["usuario_nome"] = user["nome"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", erro="Usuário ou senha inválidos.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════
#  PÁGINAS PRINCIPAIS
# ══════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM estoque_item")
    total_itens = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM estoque_item WHERE quantidade <= estoque_min")
    alertas = cur.fetchone()["total"]
    cur.execute("""
        SELECT m.tipo, m.quantidade, m.criado_em
        FROM estoque_movimento m
        ORDER BY m.criado_em DESC
        LIMIT 30
    """)
    movimentos = cur.fetchall()
    cur.close()
    return render_template("dashboard.html",
                           total_itens=total_itens,
                           alertas=alertas,
                           movimentos=movimentos)


@app.route("/entrada")
@login_required
def entrada():
    return render_template("entrada.html")


@app.route("/retirada")
@login_required
def retirada():
    return render_template("retirada.html")


@app.route("/itens")
@login_required
def itens():
    search = request.args.get("q", "").strip()
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""
            SELECT * FROM estoque_item
            WHERE codigo_peca LIKE %s OR nome_peca LIKE %s OR cliente LIKE %s
            ORDER BY nome_peca
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cur.execute("SELECT * FROM estoque_item ORDER BY nome_peca")
    rows = cur.fetchall()
    cur.close()
    return render_template("itens.html", itens=rows, search=search)


@app.route("/historico")
@login_required
def historico():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT m.*, i.nome_peca, i.codigo_peca
        FROM estoque_movimento m
        JOIN estoque_item i ON i.id = m.item_id
        ORDER BY m.criado_em DESC
        LIMIT 200
    """)
    rows = cur.fetchall()
    cur.close()
    return render_template("historico.html", movimentos=rows)


# ══════════════════════════════════════════════════════════════
#  API JSON — consumida pelo frontend mobile
# ══════════════════════════════════════════════════════════════

@app.route("/api/pecas-erp")
@login_required
def api_pecas_erp():
    """Proxy para buscar peças do Stork ERP via API REST."""
    q = request.args.get("q", "")
    data = stork_api_get(f"/api/v1/pecas?search={q}")
    if data is None:
        return jsonify({"erro": "ERP indisponível"}), 503
    return jsonify(data)


@app.route("/api/item/<codigo>")
@login_required
def api_item_por_codigo(codigo):
    """Retorna dados do item pelo código de barras (usado após leitura da câmera)."""
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM estoque_item WHERE codigo_peca = %s", (codigo,))
    item = cur.fetchone()
    cur.close()
    if not item:
        return jsonify({"erro": "Peça não encontrada"}), 404
    return jsonify(item)


@app.route("/api/entrada", methods=["POST"])
@login_required
def api_entrada():
    """Registra entrada de item no estoque e salva movimento."""
    data = request.get_json(silent=True) or {}

    codigo    = data.get("codigo_peca", "").strip()
    nome      = data.get("nome_peca", "").strip()
    cliente   = data.get("cliente", "").strip()
    quantidade = int(data.get("quantidade", 0))
    local     = data.get("local", "").strip()
    obs       = data.get("observacao", "").strip()

    if not codigo or quantidade <= 0:
        return jsonify({"erro": "Campos obrigatórios ausentes"}), 400

    cur = mysql.connection.cursor()

    # Upsert: se já existe, soma a quantidade
    cur.execute("SELECT id, quantidade FROM estoque_item WHERE codigo_peca = %s", (codigo,))
    existente = cur.fetchone()

    if existente:
        nova_qtd = existente["quantidade"] + quantidade
        cur.execute(
            "UPDATE estoque_item SET quantidade = %s, local = %s, observacao = %s WHERE id = %s",
            (nova_qtd, local, obs, existente["id"])
        )
        item_id = existente["id"]
    else:
        cur.execute("""
            INSERT INTO estoque_item (codigo_peca, nome_peca, cliente, quantidade, local, observacao)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (codigo, nome, cliente, quantidade, local, obs))
        item_id = cur.lastrowid

    cur.execute("""
        INSERT INTO estoque_movimento (item_id, tipo, quantidade, usuario_id, observacao)
        VALUES (%s, 'entrada', %s, %s, %s)
    """, (item_id, quantidade, session["usuario_id"], obs))

    mysql.connection.commit()
    cur.close()
    return jsonify({"ok": True, "item_id": item_id})


@app.route("/api/retirada", methods=["POST"])
@login_required
def api_retirada():
    """Registra retirada de item. Valida saldo antes de deduzir."""
    data = request.get_json(silent=True) or {}

    codigo    = data.get("codigo_peca", "").strip()
    quantidade = int(data.get("quantidade", 0))
    obs       = data.get("observacao", "").strip()

    if not codigo or quantidade <= 0:
        return jsonify({"erro": "Campos obrigatórios ausentes"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, quantidade FROM estoque_item WHERE codigo_peca = %s", (codigo,))
    item = cur.fetchone()

    if not item:
        cur.close()
        return jsonify({"erro": "Peça não encontrada no estoque"}), 404

    if item["quantidade"] < quantidade:
        cur.close()
        return jsonify({
            "erro": f"Saldo insuficiente. Disponível: {item['quantidade']}"
        }), 409

    cur.execute(
        "UPDATE estoque_item SET quantidade = quantidade - %s WHERE id = %s",
        (quantidade, item["id"])
    )
    cur.execute("""
        INSERT INTO estoque_movimento (item_id, tipo, quantidade, usuario_id, observacao)
        VALUES (%s, 'saida', %s, %s, %s)
    """, (item["id"], quantidade, session["usuario_id"], obs))

    mysql.connection.commit()
    cur.close()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════
#  ETIQUETA
# ══════════════════════════════════════════════════════════════

@app.route("/etiqueta/<int:item_id>")
@login_required
def etiqueta(item_id):
    """Gera e retorna PDF da etiqueta para download/impressão."""
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM estoque_item WHERE id = %s", (item_id,))
    item = cur.fetchone()
    cur.close()

    if not item:
        abort(404)

    pdf_bytes = gerar_etiqueta_pdf(item)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"etiqueta_{item['codigo_peca']}.pdf"
    )


# ══════════════════════════════════════════════════════════════
#  PWA — manifest e service worker
# ══════════════════════════════════════════════════════════════

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "Stork Estoque",
        "short_name": "Estoque",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0d0d0d",
        "theme_color": "#00e5ff",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })


@app.route("/sw.js")
def service_worker():
    """Service worker básico para instalação como PWA."""
    sw = """
const CACHE = 'stork-estoque-v1';
const ASSETS = ['/', '/entrada', '/retirada', '/static/css/estoque.css'];
self.addEventListener('install', e =>
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)))
);
self.addEventListener('fetch', e =>
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)))
);
"""
    from flask import Response
    return Response(sw, mimetype="application/javascript")


# ══════════════════════════════════════════════════════════════
#  INIT DB — cria tabelas se não existirem
# ══════════════════════════════════════════════════════════════

def init_db():
    with app.app_context():
        cur = mysql.connection.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuario (
                id       INT AUTO_INCREMENT PRIMARY KEY,
                nome     VARCHAR(100) NOT NULL,
                usuario  VARCHAR(50) UNIQUE NOT NULL,
                senha    VARCHAR(64) NOT NULL,
                ativo    TINYINT DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS estoque_item (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                codigo_peca  VARCHAR(30) NOT NULL UNIQUE,
                nome_peca    VARCHAR(150) NOT NULL,
                cliente      VARCHAR(100),
                quantidade   INT NOT NULL DEFAULT 0,
                estoque_min  INT NOT NULL DEFAULT 0,
                local        VARCHAR(60),
                observacao   TEXT,
                criado_em    DATETIME DEFAULT CURRENT_TIMESTAMP,
                atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS estoque_movimento (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                item_id     INT NOT NULL,
                tipo        ENUM('entrada','saida') NOT NULL,
                quantidade  INT NOT NULL,
                usuario_id  INT,
                observacao  TEXT,
                criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES estoque_item(id)
            )
        """)
        # Usuário admin padrão (senha: stork123)
        cur.execute("""
            INSERT IGNORE INTO usuario (nome, usuario, senha)
            VALUES ('Administrador', 'admin', MD5('stork123'))
        """)
        mysql.connection.commit()
        cur.close()


# ══════════════════════════════════════════════════════════════
#  Inicializa o banco ao subir (funciona com Gunicorn e flask run)
# ══════════════════════════════════════════════════════════════
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)