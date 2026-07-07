from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, get_current_user

router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
)


class RoleCreate(BaseModel):
    role_name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    role_name: str
    description: str | None = None


@router.get("")
def get_roles(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, role_name, description, created_at, updated_at
            FROM roles
            ORDER BY id DESC
        """)
        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_role(
    payload: RoleCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM roles WHERE role_name=%s",
            (payload.role_name,),
        )

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Role already exists")

        cursor.execute(
            """
            INSERT INTO roles (role_name, description)
            VALUES (%s, %s)
            """,
            (payload.role_name, payload.description),
        )

        db.commit()

        return {
            "message": "Role created",
            "role_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{role_id}")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM roles WHERE id=%s", (role_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Role not found")

        cursor.execute(
            """
            SELECT id FROM roles
            WHERE role_name=%s AND id != %s
            """,
            (payload.role_name, role_id),
        )

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Role name already exists")

        cursor.execute(
            """
            UPDATE roles
            SET role_name=%s, description=%s
            WHERE id=%s
            """,
            (payload.role_name, payload.description, role_id),
        )

        db.commit()

        return {
            "message": "Role updated",
            "role_id": role_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM roles WHERE id=%s", (role_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Role not found")

        cursor.execute(
            "SELECT id FROM users WHERE role_id=%s LIMIT 1",
            (role_id,),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="This role is being used by users"
            )

        cursor.execute("DELETE FROM roles WHERE id=%s", (role_id,))
        db.commit()

        return {
            "message": "Role deleted",
            "role_id": role_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()