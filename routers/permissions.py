from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, require_permission


router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"]
)


class RolePermissionUpdate(BaseModel):
    permission_ids: list[int]


@router.get("")
def get_permissions(
    current_user: dict = Depends(require_permission("manage_roles")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                permission_key,
                permission_name,
                description,
                created_at
            FROM permissions
            ORDER BY id ASC
        """)
        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.get("/roles/{role_id}")
def get_role_permissions(
    role_id: int,
    current_user: dict = Depends(require_permission("manage_roles")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, role_name FROM roles WHERE id=%s", (role_id,))
        role = cursor.fetchone()

        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        cursor.execute("""
            SELECT
                p.id,
                p.permission_key,
                p.permission_name,
                p.description,
                CASE
                    WHEN rp.id IS NULL THEN 0
                    ELSE 1
                END AS checked
            FROM permissions p
            LEFT JOIN role_permissions rp
                ON p.id = rp.permission_id
                AND rp.role_id = %s
            ORDER BY p.id ASC
        """, (role_id,))

        return {
            "role": role,
            "permissions": cursor.fetchall()
        }

    finally:
        cursor.close()
        db.close()


@router.post("/roles/{role_id}")
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    current_user: dict = Depends(require_permission("manage_roles")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM roles WHERE id=%s", (role_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Role not found")

        if payload.permission_ids:
            placeholders = ",".join(["%s"] * len(payload.permission_ids))
            cursor.execute(
                f"SELECT id FROM permissions WHERE id IN ({placeholders})",
                tuple(payload.permission_ids),
            )

            found = cursor.fetchall()
            if len(found) != len(set(payload.permission_ids)):
                raise HTTPException(
                    status_code=400,
                    detail="Some permission ids not found"
                )

        cursor.execute(
            "DELETE FROM role_permissions WHERE role_id=%s",
            (role_id,),
        )

        for permission_id in payload.permission_ids:
            cursor.execute(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (%s, %s)
                """,
                (role_id, permission_id),
            )

        db.commit()

        return {
            "message": "Role permissions updated",
            "role_id": role_id,
            "permission_ids": payload.permission_ids
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()