from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import psycopg2

app = FastAPI()

def get_db():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Database URL not configured")
    return psycopg2.connect(DATABASE_URL)

@app.get("/")
def read_root():
    return {"status": "success", "message": "Bunker INJUL online y seguro"}

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Crear tabla si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255),
                content_type VARCHAR(100)
            );
        """)
        
        # Registrar metadatos del archivo subido
        cur.execute("INSERT INTO uploaded_files (filename, content_type) VALUES (%s, %s);", 
                    (file.filename, file.content_type))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {"filename": file.filename, "status": "Archivo registrado correctamente en Postgres"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

