from datetime import datetime, timedelta
import os
import shutil
import uuid
from ftplib import FTP
import tempfile


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
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "180"))

FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "https://corteva.found-express.com,"
    "http://localhost:3000,"
    "http://localhost:5173"
).split(",")

# ========================
# FTP image
# ========================
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASSWORD = os.getenv("FTP_PASSWORD")
FTP_UPLOAD_BASE_DIR = os.getenv("FTP_UPLOAD_BASE_DIR")
FTP_PUBLIC_BASE_URL = os.getenv("FTP_PUBLIC_BASE_URL")

# ========================
# Config
# ========================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# ========================
# App
# ========================
app = FastAPI(title="Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in FRONTEND_ORIGINS
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ========================
# DB
# ========================
def get_db():
    db = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )
    return db

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

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT 
                u.id,
                u.username,
                u.email,
                u.role_id,
                r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id=%s
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            raise credentials_exception

        return user

    finally:
        cursor.close()
        db.close()       



def ensure_ftp_dir(ftp: FTP, path: str):
    parts = path.strip("/").split("/")
    ftp.cwd("/")

    for part in parts:
        try:
            ftp.mkd(part)
        except Exception:
            pass

        ftp.cwd(part)


def save_image_to_ftp(file: UploadFile):
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only jpg/png/webp allowed")

    if not FTP_HOST or not FTP_USER or not FTP_PASSWORD or not FTP_UPLOAD_BASE_DIR or not FTP_PUBLIC_BASE_URL:
        raise HTTPException(status_code=500, detail="FTP config is missing")

    month_folder = datetime.now().strftime("%Y-%m")
    file_ext = file.filename.split(".")[-1].lower()
    unique_name = str(uuid.uuid4())[:8] + "." + file_ext

    ftp_folder = f"{FTP_UPLOAD_BASE_DIR}/{month_folder}"
    public_url = f"{FTP_PUBLIC_BASE_URL}/{month_folder}/{unique_name}"

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        ftp = FTP(FTP_HOST, timeout=30)
        ftp.login(FTP_USER, FTP_PASSWORD)

        ensure_ftp_dir(ftp, ftp_folder)

        with open(temp_path, "rb") as f:
            ftp.storbinary(f"STOR {unique_name}", f)

        ftp.quit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FTP upload failed: {str(e)}")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return public_url

# ========================
# Schemas
# ========================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role_id: int | None = None


class UserUpdate(BaseModel):
    username: str
    email: str
    password: str | None = None
    role_id: int | None = None

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

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.email,
                u.password,
                u.role_id,
                r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.username=%s
            """,
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

        # ดึง Permission ของผู้ใช้
        permissions = get_user_permissions(user["id"])

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,

            "user_id": user["id"],
            "username": user["username"],
            "email": user["email"],

            "role_id": user["role_id"],
            "role_name": user["role_name"],

            # ส่ง permission ทั้งหมดที่ผู้ใช้มี
            **permissions,
        }

    finally:
        cursor.close()
        db.close()

@app.get("/me", tags=["Auth"])
def me(current_user: dict = Depends(get_current_user)):
    return current_user

# ========================
# Users Profile
# ========================
@app.get("/users/{user_id}/profile", tags=["Manage Users & Profile"])
def get_user_profile(user_id: int, current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
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

    finally:
        cursor.close()
        db.close()

# ========================
# roles
# ========================


def has_permission(user_id: int, permission_key: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT p.id
            FROM users u
            JOIN roles r ON u.role_id = r.id
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id=%s AND p.permission_key=%s
            """,
            (user_id, permission_key),
        )

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        db.close()


def get_user_permissions(user_id: int):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT p.permission_key
            FROM users u
            JOIN role_permissions rp ON u.role_id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id=%s
        """, (user_id,))

        rows = cursor.fetchall()

        permissions = {}

        for row in rows:
            permissions[row["permission_key"]] = 1

        return permissions

    finally:
        cursor.close()
        db.close()


def require_permission(permission_key: str):
    def checker(current_user: dict = Depends(get_current_user)):
        allowed = has_permission(current_user["id"], permission_key)

        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission_key}"
            )

        return current_user

    return checker


from routers.roles import router as roles_router
app.include_router(roles_router)

# ========================
# Users
# ========================
@app.get("/users", tags=["Manage Users"])
def get_users(current_user: dict = Depends(require_permission("manage_users"))):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.email,
                u.role_id,
                r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            ORDER BY u.id DESC
        """)
        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@app.post("/users", tags=["Manage Users"])
def create_user(
    user: UserCreate,
    current_user: dict = Depends(require_permission("manage_users")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM users WHERE username=%s OR email=%s",
            (user.username, user.email),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username หรือ Email ถูกใช้งานแล้ว")

        if user.role_id:
            cursor.execute("SELECT id FROM roles WHERE id=%s", (user.role_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

        hashed_password = hash_password(user.password)

        cursor.execute(
            """
            INSERT INTO users (username, email, password, role_id)
            VALUES (%s, %s, %s, %s)
            """,
            (user.username, user.email, hashed_password, user.role_id),
        )
        db.commit()

        return {
            "message": "User created",
            "user_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()

@app.put("/users/{user_id}", tags=["Manage Users"])
def update_user(
    user_id: int,
    user: UserUpdate,
    current_user: dict = Depends(require_permission("manage_users"))
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute(
            "SELECT id FROM users WHERE (username=%s OR email=%s) AND id != %s",
            (user.username, user.email, user_id),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username หรือ Email ถูกใช้งานแล้ว")

        if user.role_id:
            cursor.execute(
                "SELECT id FROM roles WHERE id=%s",
                (user.role_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

        if user.password:
            cursor.execute(
                """
                UPDATE users
                SET username=%s,
                    email=%s,
                    password=%s,
                    role_id=%s
                WHERE id=%s
                """,
                (
                    user.username,
                    user.email,
                    hash_password(user.password),
                    user.role_id,
                    user_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE users
                SET username=%s,
                    email=%s,
                    role_id=%s
                WHERE id=%s
                """,
                (
                    user.username,
                    user.email,
                    user.role_id,
                    user_id,
                ),
            )

        db.commit()

        return {
            "message": "User updated",
            "user_id": user_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()




@app.delete("/users/{user_id}", tags=["Manage Users"])
def delete_user(
    user_id: int,
    current_user: dict = Depends(require_permission("manage_users")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("DELETE FROM people WHERE user_id=%s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        db.commit()

        return {"message": "User deleted"}

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()

# ========================
# People
# ========================
@app.get("/people", tags=["Manage People"])
def get_people(current_user: dict = Depends(require_permission("manage_users"))):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
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

    finally:
        cursor.close()
        db.close()

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
    current_user: dict = Depends(require_permission("manage_users")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("SELECT id FROM people WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Profile already exists")

        image_path = None
        if profile_image:
            image_path = save_image_to_ftp(profile_image)

        sql = """
            INSERT INTO people
            (user_id, first_name, last_name, nickname, phone, age, job, profile_image)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            sql,
            (
                user_id,
                first_name,
                last_name,
                nickname,
                phone,
                age,
                job,
                image_path,
            ),
        )

        db.commit()

        return {
            "message": "Person created",
            "profile_image": image_path,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()



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
    current_user: dict = Depends(require_permission("manage_users")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM people WHERE id=%s", (person_id,))
        person = cursor.fetchone()

        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        image_path = person["profile_image"]

        if profile_image:
            image_path = save_image_to_ftp(profile_image)

        sql = """
            UPDATE people
            SET first_name=%s,
                last_name=%s,
                nickname=%s,
                phone=%s,
                age=%s,
                job=%s,
                profile_image=%s
            WHERE id=%s
        """

        cursor.execute(
            sql,
            (
                first_name,
                last_name,
                nickname,
                phone,
                age,
                job,
                image_path,
                person_id,
            ),
        )

        db.commit()

        return {
            "message": "Person updated",
            "profile_image": image_path,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@app.delete("/people/{person_id}", tags=["Manage People"])
def delete_person(
    person_id: int,
    current_user: dict = Depends(require_permission("manage_users")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM people WHERE id=%s", (person_id,))
        person = cursor.fetchone()

        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        cursor.execute("DELETE FROM people WHERE id=%s", (person_id,))
        db.commit()

        return {"message": "Person deleted"}

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()
        

# import router หลังจากมี get_db/get_current_user แล้ว
from routers.weedy_rice import router as weedy_rice_router
app.include_router(weedy_rice_router)


from routers.projects import router as projects_router
app.include_router(projects_router)


from routers.treatments import router as treatments_router
app.include_router(treatments_router)

from routers.trials import router as trials_router
app.include_router(trials_router)

from routers.plots import router as plots_router
app.include_router(plots_router)

from routers.observations import router as observations_router
app.include_router(observations_router)

from routers.measurements import router as measurements_router
app.include_router(measurements_router)

from routers.permissions import router as permissions_router
app.include_router(permissions_router)


from routers.varieties import router as varieties_router
app.include_router(varieties_router)

from routers.products import router as products_router
app.include_router(products_router)

from routers.project_members import router as project_members_router
app.include_router(project_members_router)


from routers.dashboard import router as dashboard_router
app.include_router(dashboard_router)
# ========================
# Run local:
# uvicorn main:app --reload
#
# Run deploy Railway:
# uvicorn main:app --host 0.0.0.0 --port $PORT
# ========================