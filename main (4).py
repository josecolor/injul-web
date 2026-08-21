import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
import json
import asyncio
import time
import secrets
import hashlib
import requests
import psycopg2
import psycopg2.extras
from PIL import Image
from io import BytesIO

app = FastAPI()
UPLOAD_DIR = "/data"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# Configuración de Resend (envío de correo por API, evita el bloqueo de puertos SMTP de Railway)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")
RESEND_DEST = os.getenv("RESEND_DEST", "jose.colorvision@gmail.com")

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


# Formulario de contacto — envía por la API HTTPS de Resend en vez de SMTP directo
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
        return JSONResponse(
            status_code=400,
            content={"ok": False, "msg": "Complete los campos obligatorios."},
        )

    asunto = f"Consulta web: {servicio} - {nombre}"
    html = f"""<h3>Nueva consulta desde la web</h3>
    <p><b>Nombre:</b> {nombre} <br>
    <b>Correo:</b> {correo} <br>
    <b>Teléfono:</b> {telefono} <br>
    <b>Servicio:</b> {servicio} </p>
    <p><b>Mensaje:</b><br>{mensaje}</p>"""

    if not RESEND_API_KEY:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "msg": "Fallo: falta configurar RESEND_API_KEY"},
        )

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [RESEND_DEST],
                "subject": asunto,
                "html": html,
                "reply_to": correo,
            },
            timeout=15,
        )

        if resp.status_code in (200, 201):
            return JSONResponse(content={"ok": True, "msg": "¡Mensaje enviado con éxito!"})
        else:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "msg": f"Fallo: {resp.status_code} - {resp.text}"},
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "msg": f"Fallo: {str(e)}"},
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
