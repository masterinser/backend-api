from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/varieties",
    tags=["Varieties"]
)


class VarietyCreate(BaseModel):
    variety_name: str
    description: str | None = None
    status: int = 1


class VarietyUpdate(BaseModel):
    variety_name: str
    description: str | None = None
    status: int = 1


@router.get("")
def get_varieties(
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        if has_permission(current_user["id"], "view_all_projects"):

            cursor.execute("""
                SELECT *
                FROM varieties
                ORDER BY variety_name
            """)

        else:

            cursor.execute("""
                SELECT *
                FROM varieties
                WHERE created_by=%s
                ORDER BY variety_name
            """, (current_user["id"],))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_variety(
    payload: VarietyCreate,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT id
            FROM varieties
            WHERE variety_name=%s
            AND created_by=%s
        """, (
            payload.variety_name,
            current_user["id"],
        ))

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Variety already exists"
            )

        cursor.execute("""
            INSERT INTO varieties
            (
                variety_name,
                description,
                status,
                created_by
            )
            VALUES
            (%s,%s,%s,%s)
        """, (
            payload.variety_name,
            payload.description,
            payload.status,
            current_user["id"],
        ))

        db.commit()

        return {
            "message": "Variety created",
            "variety_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{variety_id}")
def update_variety(
    variety_id: int,
    payload: VarietyUpdate,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        if has_permission(current_user["id"], "view_all_projects"):

            cursor.execute("""
                SELECT id
                FROM varieties
                WHERE id=%s
            """, (variety_id,))

        else:

            cursor.execute("""
                SELECT id
                FROM varieties
                WHERE id=%s
                AND created_by=%s
            """, (
                variety_id,
                current_user["id"],
            ))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own variety"
            )

        cursor.execute("""
            UPDATE varieties
            SET
                variety_name=%s,
                description=%s,
                status=%s
            WHERE id=%s
        """, (
            payload.variety_name,
            payload.description,
            payload.status,
            variety_id,
        ))

        db.commit()

        return {
            "message": "Variety updated"
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{variety_id}")
def delete_variety(
    variety_id: int,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        if has_permission(current_user["id"], "view_all_projects"):

            cursor.execute("""
                SELECT id
                FROM varieties
                WHERE id=%s
            """, (variety_id,))

        else:

            cursor.execute("""
                SELECT id
                FROM varieties
                WHERE id=%s
                AND created_by=%s
            """, (
                variety_id,
                current_user["id"],
            ))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own variety"
            )

        cursor.execute(
            "DELETE FROM varieties WHERE id=%s",
            (variety_id,),
        )

        db.commit()

        return {
            "message": "Variety deleted"
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()