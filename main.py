from datetime import datetime, timedelta
import os
import shutil
import uuid

import mysql.connector
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from dotenv import load_dotenv

# ========================
# Load ENV
# ========================
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "backend_db")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

SECRET_KEY = os.getenv("SECRET_KEY", "please_change_this_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ใส่โดเมน frontend จริงตอน deploy เช่น https://yourdomain.com
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

# ========================
# Config
# ========================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

UPLOAD_DIR = "upload/people"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ========================
# App
# ========================
app = FastAPI(title="Backend API")

app.mount("/upload", StaticFiles(directory="upload"), name="upload")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in FRONTEND_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# DB
# ========================
db = mysql.connector.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    autocommit=False,
)
cursor = db.cursor(dictionary=True)

# ========================
# Utils
# ========================
def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token ไม่ถูกต้อง หรือหมดอายุแล้ว",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    cursor.execute(
        "SELECT id, username, email FROM users WHERE id=%s",
        (user_id,),
    )
    user = cursor.fetchone()

    if not user:
        raise credentials_exception

    return user


def save_image(file: UploadFile):
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only jpg/png allowed")

    file_ext = file.filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = f"{UPLOAD_DIR}/{unique_name}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path

# ========================
# Schemas
# ========================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(BaseModel):
    username: str
    email: str
    password: str | None = None


class PersonUpdate(BaseModel):
    first_name: str
    last_name: str
    nickname: str | None = None
    phone: str
    age: int
    job: str

# ========================
# Root / Health
# ========================
@app.get("/", tags=["Root"])
def root():
    return {"message": "FastAPI is running"}


@app.get("/health", tags=["Root"])
def health():
    return {"status": "ok"}

# ========================
# Auth
# ========================
@app.post("/login", tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    cursor.execute(
        "SELECT id, username, email, password FROM users WHERE username=%s",
        (form_data.username,),
    )
    user = cursor.fetchone()

    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username หรือ Password ไม่ถูกต้อง",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={
            "user_id": user["id"],
            "username": user["username"],
            "email": user["email"],
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
    }


@app.get("/me", tags=["Auth"])
def me(current_user: dict = Depends(get_current_user)):
    return current_user

# ========================
# Users Profile
# ========================
@app.get("/users/{user_id}/profile", tags=["Manage Users & Profile"])
def get_user_profile(user_id: int, current_user: dict = Depends(get_current_user)):
    sql = """
        SELECT
            u.id AS user_id,
            u.username,
            u.email,
            p.*
        FROM users u
        LEFT JOIN people p ON u.id = p.user_id
        WHERE u.id = %s
    """
    cursor.execute(sql, (user_id,))
    data = cursor.fetchone()

    if not data:
        raise HTTPException(status_code=404, detail="User not found")

    return data

# ========================
# Users
# ========================
@app.get("/users", tags=["Manage Users"])
def get_users(current_user: dict = Depends(get_current_user)):
    cursor.execute("SELECT id, username, email FROM users")
    return cursor.fetchall()


@app.post("/users", tags=["Manage Users"])
def create_user(user: UserCreate):
    """
    Endpoint นี้เปิดไว้สำหรับสร้าง user แรก/สมัครสมาชิก
    ถ้าอยากให้ต้อง login ก่อน ให้เพิ่ม:
    current_user: dict = Depends(get_current_user)
    """
    cursor.execute(
        "SELECT id FROM users WHERE username=%s OR email=%s",
        (user.username, user.email),
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Username หรือ Email ถูกใช้งานแล้ว")

    hashed_password = hash_password(user.password)

    sql = """
        INSERT INTO users (username, email, password)
        VALUES (%s, %s, %s)
    """
    cursor.execute(sql, (user.username, user.email, hashed_password))
    db.commit()

    return {"message": "User created"}


@app.put("/users/{user_id}", tags=["Manage Users"])
def update_user(user_id: int, user: UserUpdate, current_user: dict = Depends(get_current_user)):
    cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    cursor.execute(
        "SELECT id FROM users WHERE (username=%s OR email=%s) AND id != %s",
        (user.username, user.email, user_id),
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Username หรือ Email ถูกใช้งานแล้ว")

    if user.password:
        hashed_password = hash_password(user.password)
        sql = """
            UPDATE users
            SET username=%s, email=%s, password=%s
            WHERE id=%s
        """
        cursor.execute(sql, (user.username, user.email, hashed_password, user_id))
    else:
        sql = """
            UPDATE users
            SET username=%s, email=%s
            WHERE id=%s
        """
        cursor.execute(sql, (user.username, user.email, user_id))

    db.commit()
    return {"message": "User updated"}


@app.delete("/users/{user_id}", tags=["Manage Users"])
def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    cursor.execute("SELECT profile_image FROM people WHERE user_id=%s", (user_id,))
    person = cursor.fetchone()
    if person and person["profile_image"] and os.path.exists(person["profile_image"]):
        os.remove(person["profile_image"])

    cursor.execute("DELETE FROM people WHERE user_id=%s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()

    return {"message": "User deleted"}

# ========================
# People
# ========================
@app.get("/people", tags=["Manage People"])
def get_people(current_user: dict = Depends(get_current_user)):
    sql = """
        SELECT
            p.*,
            u.username,
            u.email
        FROM people p
        JOIN users u ON p.user_id = u.id
    """
    cursor.execute(sql)
    return cursor.fetchall()


@app.post("/people", tags=["Manage People"])
def create_person(
    user_id: int = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    nickname: str = Form(None),
    phone: str = Form(...),
    age: int = Form(...),
    job: str = Form(...),
    profile_image: UploadFile = File(None),
    current_user: dict = Depends(get_current_user),
):
    cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    cursor.execute("SELECT id FROM people WHERE user_id=%s", (user_id,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Profile already exists")

    image_path = None
    if profile_image:
        image_path = save_image(profile_image)

    sql = """
        INSERT INTO people
        (user_id, first_name, last_name, nickname, phone, age, job, profile_image)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(
        sql,
        (user_id, first_name, last_name, nickname, phone, age, job, image_path),
    )
    db.commit()

    return {"message": "Person created with image"}


@app.put("/people/{person_id}", tags=["Manage People"])
def update_person(
    person_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    nickname: str = Form(None),
    phone: str = Form(...),
    age: int = Form(...),
    job: str = Form(...),
    profile_image: UploadFile = File(None),
    current_user: dict = Depends(get_current_user),
):
    cursor.execute("SELECT * FROM people WHERE id=%s", (person_id,))
    person = cursor.fetchone()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    image_path = person["profile_image"]

    if profile_image:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        image_path = save_image(profile_image)

    sql = """
        UPDATE people
        SET first_name=%s, last_name=%s, nickname=%s,
            phone=%s, age=%s, job=%s, profile_image=%s
        WHERE id=%s
    """
    cursor.execute(
        sql,
        (first_name, last_name, nickname, phone, age, job, image_path, person_id),
    )
    db.commit()

    return {"message": "Person updated"}


@app.delete("/people/{person_id}", tags=["Manage People"])
def delete_person(person_id: int, current_user: dict = Depends(get_current_user)):
    cursor.execute("SELECT profile_image FROM people WHERE id=%s", (person_id,))
    person = cursor.fetchone()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person["profile_image"] and os.path.exists(person["profile_image"]):
        os.remove(person["profile_image"])

    cursor.execute("DELETE FROM people WHERE id=%s", (person_id,))
    db.commit()

    return {"message": "Person deleted"}

# ========================
# Run local:
# uvicorn main:app --reload
#
# Run deploy Railway:
# uvicorn main:app --host 0.0.0.0 --port $PORT
# ========================
