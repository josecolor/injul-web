import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
import json
import asyncio
import time
import secrets
import hashlib
import base64
from urllib.parse import urlencode
from email.mime.text import MIMEText
import requests
import psycopg2
import psycopg2.extras
from PIL import Image
from io import BytesIO
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

app = FastAPI()
UPLOAD_DIR = "/data"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# ── Configuración de envío de correo por Gmail API (OAuth) ──────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
GMAIL_SEND_ADDRESS = os.getenv("GMAIL_SEND_ADDRESS", "injul01@gmail.com")
NOTIFY_DEST = os.getenv("RESEND_DEST", "jose.colorvision@gmail.com")

# Sirve wp-content e imagenesweb como archivos estáticos
if os.path.isdir(os.path.join(SITE_DIR, "wp-content")):
    app.mount("/wp-content", StaticFiles(directory=os.path.join(SITE_DIR, "wp-content")), name="wp-content")
if os.path.isdir(os.path.join(SITE_DIR, "imagenesweb")):
    app.mount("/imagenesweb", StaticFiles(directory=os.path.join(SITE_DIR, "imagenesweb")), name="imagenesweb")


def serve_page(filename: str):
    file_path = os.path.join(SITE_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    raise HTTPException(status_code=404, detail=f"{filename} no encontrado")


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def ensure_noticias_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS noticias (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            date TIMESTAMP NOT NULL,
            cover TEXT DEFAULT '',
            category TEXT DEFAULT 'Noticias',
            author TEXT DEFAULT 'INJUL',
            excerpt TEXT DEFAULT '',
            published BOOLEAN DEFAULT TRUE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def seed_noticias_if_empty():
    """Carga las 23 noticias rescatadas del sitio original, solo si la tabla está vacía."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM noticias;")
    count = cur.fetchone()[0]
    if count == 0:
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noticias_seed.json")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                noticias = json.load(f)
            ok, fail = 0, 0
            for n in noticias:
                try:
                    cur.execute(
                        """INSERT INTO noticias (title, content, date, cover, category, author, excerpt, published)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            n.get("title", ""),
                            n.get("content", ""),
                            n.get("date"),
                            n.get("cover", ""),
                            n.get("category", "Noticias"),
                            n.get("author", "INJUL"),
                            n.get("excerpt", ""),
                            n.get("published", True),
                        ),
                    )
                    conn.commit()
                    ok += 1
                except Exception as e:
                    conn.rollback()
                    fail += 1
                    print(f"SEED ERROR en '{n.get('title','?')[:40]}': {e}")
            print(f"SEED RESULT: {ok} insertadas, {fail} fallidas de {len(noticias)}")
    cur.close()
    conn.close()


@app.post("/api/reseed-noticias")
async def reseed_noticias():
    """Endpoint temporal: borra todas las noticias y las recarga desde el seed, reportando errores por artículo."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM noticias;")
    conn.commit()
    cur.close()
    conn.close()

    seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noticias_seed.json")
    if not os.path.exists(seed_path):
        return JSONResponse(status_code=404, content={"error": "noticias_seed.json no encontrado"})

    with open(seed_path, "r", encoding="utf-8") as f:
        noticias = json.load(f)

    conn = get_db_connection()
    cur = conn.cursor()
    ok, errores = 0, []
    for n in noticias:
        try:
            cur.execute(
                """INSERT INTO noticias (title, content, date, cover, category, author, excerpt, published)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    n.get("title", ""),
                    n.get("content", ""),
                    n.get("date"),
                    n.get("cover", ""),
                    n.get("category", "Noticias"),
                    n.get("author", "INJUL"),
                    n.get("excerpt", ""),
                    n.get("published", True),
                ),
            )
            conn.commit()
            ok += 1
        except Exception as e:
            conn.rollback()
            errores.append({"title": n.get("title", "?")[:60], "error": str(e)})
    cur.close()
    conn.close()

    return JSONResponse(content={"insertadas": ok, "total": len(noticias), "errores": errores})


SERVER_START_TIME = time.time()


async def keep_alive_loop():
    """Se hace ping a sí mismo cada 4 minutos para evitar que Railway duerma el servicio por inactividad."""
    own_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    await asyncio.sleep(30)
    while True:
        try:
            if own_url:
                requests.get(f"https://{own_url}/health", timeout=10)
        except Exception as e:
            print(f"Keep-alive ping falló: {e}")
        await asyncio.sleep(240)


@app.get("/health")
async def health_check():
    uptime = round(time.time() - SERVER_START_TIME)
    return JSONResponse(content={"status": "ok", "uptime_seconds": uptime})


@app.on_event("startup")
async def startup_event():
    try:
        ensure_noticias_table()
        seed_noticias_if_empty()
    except Exception as e:
        print(f"Aviso: no se pudo inicializar noticias ({e})")
    asyncio.create_task(keep_alive_loop())


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return serve_page("index.html")


@app.get("/index.html", response_class=HTMLResponse)
async def serve_index_html():
    return serve_page("index.html")


@app.get("/nosotros.html", response_class=HTMLResponse)
async def serve_nosotros():
    return serve_page("nosotros.html")


@app.get("/noticias.html", response_class=HTMLResponse)
async def serve_noticias():
    return serve_page("noticias.html")


@app.get("/noticia.html", response_class=HTMLResponse)
async def serve_noticia():
    return serve_page("noticia.html")


@app.get("/admin-login.html", response_class=HTMLResponse)
async def serve_admin_login():
    return serve_page("admin-login.html")


@app.get("/panel.html", response_class=HTMLResponse)
async def serve_panel():
    return serve_page("panel.html")


@app.get("/perfiles.html", response_class=HTMLResponse)
async def serve_perfiles():
    return serve_page("perfiles.html")


@app.get("/admin.html", response_class=HTMLResponse)
async def serve_admin():
    return serve_page("admin.html")


# API de noticias — sirve los artículos reales desde PostgreSQL a todos los visitantes
@app.get("/api/noticias")
async def api_get_noticias():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM noticias WHERE published = TRUE ORDER BY date DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        noticias = []
        for r in rows:
            noticias.append({
                "id": r["id"],
                "title": r["title"],
                "content": r["content"],
                "date": r["date"].isoformat() if r["date"] else "",
                "cover": r["cover"],
                "category": r["category"],
                "author": r["author"],
                "excerpt": r["excerpt"],
                "published": r["published"],
            })
        return JSONResponse(content=noticias)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Panel de administración (CMS) ────────────────────────────────────
ACTIVE_TOKENS = set()  # tokens de sesión válidos en memoria


def ensure_admin_settings_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def get_stored_password_hash():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM admin_settings WHERE key = 'admin_pw_hash';")
    row = cur.fetchone()
    cur.execute("SELECT value FROM admin_settings WHERE key = 'admin_pw_salt';")
    salt_row = cur.fetchone()
    cur.close()
    conn.close()
    if row and salt_row:
        return row[0], salt_row[0]
    return None, None


@app.get("/api/admin-status")
async def admin_status():
    """Indica si el equipo ya configuró su contraseña de acceso."""
    ensure_admin_settings_table()
    pw_hash, _ = get_stored_password_hash()
    return JSONResponse(content={"configured": pw_hash is not None})


@app.post("/api/admin-setup")
async def admin_setup(request: Request):
    """Primera vez: el equipo crea su propia contraseña. Solo funciona si aún no hay una guardada."""
    ensure_admin_settings_table()
    existing, _ = get_stored_password_hash()
    if existing is not None:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "Ya existe una contraseña configurada."})

    body = await request.json()
    password = (body.get("password") or "").strip()
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "La contraseña debe tener al menos 6 caracteres."})

    salt = secrets.token_hex(16)
    pw_hash = hash_password(password, salt)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_settings (key, value) VALUES ('admin_pw_hash', %s), ('admin_pw_salt', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
        (pw_hash, salt),
    )
    conn.commit()
    cur.close()
    conn.close()
    return JSONResponse(content={"ok": True})


def check_admin_token(request: Request):
    token = request.headers.get("X-Admin-Token", "")
    if not token or token not in ACTIVE_TOKENS:
        raise HTTPException(status_code=401, detail="No autorizado")


@app.post("/api/admin-login")
async def admin_login(request: Request):
    body = await request.json()
    password = body.get("password", "")
    stored_hash, salt = get_stored_password_hash()
    if stored_hash is None:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "Aún no se ha configurado una contraseña."})
    if hash_password(password, salt) == stored_hash:
        token = secrets.token_hex(24)
        ACTIVE_TOKENS.add(token)
        return JSONResponse(content={"ok": True, "token": token})
    return JSONResponse(content={"ok": False, "msg": "Contraseña incorrecta"})


@app.post("/api/admin-forgot-password")
async def admin_forgot_password(request: Request):
    """Restablece la contraseña usando la clave de recuperación (RECOVERY_KEY), sin necesitar la contraseña anterior."""
    recovery_key_env = os.getenv("RECOVERY_KEY", "")
    body = await request.json()
    recovery_key = (body.get("recovery_key") or "").strip()
    new_password = (body.get("new_password") or "").strip()

    if not recovery_key_env:
        return JSONResponse(status_code=500, content={"ok": False, "msg": "Recuperación no configurada en el servidor."})
    if recovery_key != recovery_key_env:
        return JSONResponse(status_code=403, content={"ok": False, "msg": "Clave de recuperación incorrecta."})
    if len(new_password) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "La contraseña debe tener al menos 6 caracteres."})

    ensure_admin_settings_table()
    salt = secrets.token_hex(16)
    pw_hash = hash_password(new_password, salt)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_settings (key, value) VALUES ('admin_pw_hash', %s), ('admin_pw_salt', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
        (pw_hash, salt),
    )
    conn.commit()
    cur.close()
    conn.close()
    ACTIVE_TOKENS.clear()  # cierra todas las sesiones activas por seguridad
    return JSONResponse(content={"ok": True})


@app.post("/api/admin-change-password")
async def admin_change_password(request: Request):
    """Permite al equipo cambiar su contraseña desde el panel, una vez autenticados."""
    check_admin_token(request)
    body = await request.json()
    new_password = (body.get("new_password") or "").strip()
    if len(new_password) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "La contraseña debe tener al menos 6 caracteres."})

    salt = secrets.token_hex(16)
    pw_hash = hash_password(new_password, salt)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_settings (key, value) VALUES ('admin_pw_hash', %s), ('admin_pw_salt', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
        (pw_hash, salt),
    )
    conn.commit()
    cur.close()
    conn.close()
    return JSONResponse(content={"ok": True})


@app.post("/api/admin-upload-image")
async def admin_upload_image(request: Request, image: UploadFile = File(...)):
    check_admin_token(request)
    try:
        contents = await image.read()
        img = Image.open(BytesIO(contents))
        img = img.convert("RGB")

        max_width = 1200
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)))

        upload_dir = os.path.join(SITE_DIR, "wp-content", "uploads", "cms")
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"{secrets.token_hex(8)}.jpg"
        file_path = os.path.join(upload_dir, filename)
        img.save(file_path, "JPEG", quality=80, optimize=True)

        public_path = f"/wp-content/uploads/cms/{filename}"
        return JSONResponse(content={"ok": True, "path": public_path})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "msg": str(e)})


@app.post("/api/admin-publicar")
async def admin_publicar(request: Request):
    check_admin_token(request)
    body = await request.json()
    titulo = (body.get("titulo") or "").strip()
    contenido = (body.get("contenido") or "").strip()
    destino = body.get("destino", "portada")
    cover = body.get("cover", "")

    if not titulo or not contenido:
        return JSONResponse(status_code=400, content={"ok": False, "msg": "Falta título o contenido"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO noticias (title, content, date, cover, category, author, excerpt, published)
               VALUES (%s, %s, NOW(), %s, %s, %s, %s, TRUE) RETURNING id""",
            (titulo, contenido, cover, destino, "INJUL", ""),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return JSONResponse(content={"ok": True, "id": new_id})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "msg": str(e)})


@app.delete("/api/admin-eliminar/{noticia_id}")
async def admin_eliminar(noticia_id: int, request: Request):
    check_admin_token(request)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM noticias WHERE id = %s", (noticia_id,))
        conn.commit()
        cur.close()
        conn.close()
        return JSONResponse(content={"ok": True})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "msg": str(e)})


def ensure_contact_log_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_attempts (
            id SERIAL PRIMARY KEY,
            fecha TIMESTAMP DEFAULT NOW(),
            nombre TEXT,
            correo TEXT,
            telefono TEXT,
            servicio TEXT,
            mensaje TEXT,
            exito BOOLEAN,
            detalle_error TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def log_contact_attempt(nombre, correo, telefono, servicio, mensaje, exito, detalle_error=""):
    try:
        ensure_contact_log_table()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO contact_attempts (nombre, correo, telefono, servicio, mensaje, exito, detalle_error)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (nombre, correo, telefono, servicio, mensaje[:500], exito, detalle_error[:500]),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"No se pudo registrar el intento de contacto: {e}")


@app.get("/api/contact-attempts")
async def get_contact_attempts(request: Request):
    """Panel de diagnóstico: lista los últimos intentos del formulario de contacto (requiere sesión de admin)."""
    check_admin_token(request)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM contact_attempts ORDER BY fecha DESC LIMIT 100;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    resultado = []
    for r in rows:
        resultado.append({
            "id": r["id"],
            "fecha": r["fecha"].isoformat() if r["fecha"] else "",
            "nombre": r["nombre"],
            "correo": r["correo"],
            "telefono": r["telefono"],
            "servicio": r["servicio"],
            "exito": r["exito"],
            "detalle_error": r["detalle_error"],
        })
    return JSONResponse(content=resultado)


# ── Gmail API (OAuth) — reemplaza el envío por Resend ────────────────

def _fernet():
    if not TOKEN_ENCRYPTION_KEY:
        raise RuntimeError("Falta configurar TOKEN_ENCRYPTION_KEY en las variables de entorno")
    return Fernet(TOKEN_ENCRYPTION_KEY.encode())


def save_google_refresh_token(refresh_token: str):
    ensure_admin_settings_table()
    encrypted = _fernet().encrypt(refresh_token.encode()).decode()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_settings (key, value) VALUES ('google_refresh_token_enc', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
        (encrypted,),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_google_refresh_token():
    ensure_admin_settings_table()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM admin_settings WHERE key = 'google_refresh_token_enc';")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return _fernet().decrypt(row[0].encode()).decode()


def get_gmail_access_token():
    refresh_token = get_google_refresh_token()
    if not refresh_token:
        raise RuntimeError("No hay cuenta de Gmail conectada todavía. Visita /oauth/google/start?key=TU_RECOVERY_KEY")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token


@app.get("/oauth/google/start")
async def oauth_google_start(key: str = ""):
    """Paso 1 de la autorización única: redirige a la pantalla de consentimiento de Google.
    Protegido con RECOVERY_KEY para que no cualquiera pueda iniciar la conexión."""
    if not key or key != os.getenv("RECOVERY_KEY", ""):
        raise HTTPException(status_code=403, detail="No autorizado")
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Faltan GOOGLE_CLIENT_ID / GOOGLE_REDIRECT_URI en el servidor")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.send",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)


@app.get("/oauth/google/callback")
async def oauth_google_callback(code: str = "", error: str = ""):
    """Paso 2: Google redirige aquí con el código. Lo cambiamos por un refresh_token y lo guardamos encriptado."""
    if error:
        return HTMLResponse(f"<h3>Autorización cancelada: {error}</h3>", status_code=400)
    if not code:
        return HTMLResponse("<h3>Falta el código de autorización</h3>", status_code=400)

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return HTMLResponse(
            "<h3>No se recibió un refresh_token de Google.</h3>"
            "<p>Esto suele pasar si ya habías autorizado antes. Revoca el acceso en "
            "<a href='https://myaccount.google.com/permissions' target='_blank'>myaccount.google.com/permissions</a> "
            "y vuelve a intentar desde /oauth/google/start.</p>"
            f"<pre>{json.dumps(data, indent=2)}</pre>",
            status_code=400,
        )
    save_google_refresh_token(refresh_token)
    return HTMLResponse("<h3>✅ Cuenta de Gmail conectada correctamente. Ya puedes cerrar esta ventana.</h3>")


def enviar_correo_gmail(destinatario: str, asunto: str, html: str, reply_to: str = None):
    """Envía un correo usando la Gmail API con el token guardado. Devuelve (ok, detalle)."""
    try:
        access_token = get_gmail_access_token()
    except Exception as e:
        return False, f"No se pudo obtener token de Gmail: {e}"

    msg = MIMEText(html, "html", "utf-8")
    msg["to"] = destinatario
    msg["from"] = GMAIL_SEND_ADDRESS
    msg["subject"] = asunto
    if reply_to:
        msg["reply-to"] = reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        resp = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw},
            timeout=15,
        )
        return resp.status_code in (200, 202), resp.text
    except Exception as e:
        return False, str(e)


def enviar_respuesta_automatica(nombre, correo, mensaje_original, ref):
    """Envía una respuesta de confirmación personalizada al remitente del formulario, vía Gmail."""
    saludo_nombre = nombre.strip() if nombre and nombre.strip() else None
    saludo = f"Estimado/a {saludo_nombre}" if saludo_nombre else "Estimado/a cliente"

    asunto = f"Hemos recibido su consulta — INJUL (Ref. {ref})"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #2E3E52;">
      <p style="font-size: 15px; line-height: 1.7;">
        {saludo},<br><br>
        Gracias por confiar en nosotros. Su consulta ya está en nuestras manos
        y un miembro de nuestro equipo de
        <b>Investigadores Jurídicos Leonor (INJUL)</b> la está revisando en
        este momento — <b>estamos con usted</b> desde ya, con toda la
        confidencialidad y rigor que nos caracteriza.
      </p>
      <p style="font-size: 15px; line-height: 1.7;">
        En breve nos pondremos en contacto directo con usted para darle
        seguimiento personalizado.
      </p>
      <div style="background:#F4F7FA; border-left: 3px solid #215590; padding: 14px 18px; margin: 20px 0; font-size: 14px; color: #3D4F63;">
        <b>Su mensaje:</b><br>{mensaje_original}
      </div>
      <p style="font-size: 13px; color: #7A8899;">
        Si necesita comunicarse con nosotros de inmediato, puede llamarnos al
        809-547-3178 o escribirnos a injul01@gmail.com.
      </p>
    </div>
    """
    return enviar_correo_gmail(correo, asunto, html)


@app.post("/enviar.php")
async def enviar_contacto(
    nombre: str = Form(""),
    telefono: str = Form(""),
    correo: str = Form(""),
    servicio: str = Form(""),
    mensaje: str = Form(""),
):
    nombre = nombre.strip()
    telefono = telefono.strip()
    correo = correo.strip()
    servicio = servicio.strip()
    mensaje = mensaje.strip()

    if not nombre or not correo or not mensaje:
        log_contact_attempt(nombre, correo, telefono, servicio, mensaje, False, "Campos obligatorios vacíos")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "msg": "Complete los campos obligatorios."},
        )

    ref = secrets.token_hex(4).upper()
    asunto = f"Consulta web: {servicio} - {nombre} (Ref. {ref})"
    html = f"""<h3>Nueva consulta desde la web</h3>
    <p><b>Nombre:</b> {nombre} <br>
    <b>Correo:</b> {correo} <br>
    <b>Teléfono:</b> {telefono} <br>
    <b>Servicio:</b> {servicio} </p>
    <p><b>Mensaje:</b><br>{mensaje}</p>"""

    ok, detalle = enviar_correo_gmail(NOTIFY_DEST, asunto, html, reply_to=correo)

    if ok:
        log_contact_attempt(nombre, correo, telefono, servicio, mensaje, True)
        # Respuesta automática al remitente — best-effort, no afecta la respuesta principal si falla
        ok_autoreply, detalle_autoreply = enviar_respuesta_automatica(nombre, correo, mensaje, ref)
        if not ok_autoreply:
            print(f"Aviso: respuesta automática a {correo} no se pudo enviar: {detalle_autoreply}")
        return JSONResponse(content={"ok": True, "msg": "¡Mensaje enviado con éxito!"})
    else:
        log_contact_attempt(nombre, correo, telefono, servicio, mensaje, False, detalle)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "msg": f"Fallo al enviar: {detalle}"},
        )


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS uploaded_files (id SERIAL PRIMARY KEY, filename TEXT, path TEXT);")
        cur.execute("INSERT INTO uploaded_files (filename, path) VALUES (%s, %s)", (file.filename, file_path))
        conn.commit()
        cur.close()
        conn.close()

        return {"status": "success", "message": f"Archivo {file.filename} guardado en {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
