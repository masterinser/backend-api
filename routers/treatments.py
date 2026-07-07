from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, get_current_user


router = APIRouter(
    prefix="/treatments",
    tags=["Treatments"]
)


class TreatmentCreate(BaseModel):
    project_id: int
    treatment_code: str
    treatment_name: str
    description: str | None = None
    status: int = 1


class TreatmentUpdate(BaseModel):
    treatment_code: str
    treatment_name: str
    description: str | None = None
    status: int = 1


@router.get("")
def get_treatments(
    project_id: int | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if project_id:
            cursor.execute(
                """
                SELECT *
                FROM treatments
                WHERE project_id=%s
                ORDER BY id ASC
                """,
                (project_id,),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM treatments
                ORDER BY id DESC
                """
            )

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_treatment(
    payload: TreatmentCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM projects WHERE id=%s",
            (payload.project_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")

        cursor.execute(
            """
            SELECT id FROM treatments
            WHERE project_id=%s AND treatment_code=%s
            """,
            (payload.project_id, payload.treatment_code),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Treatment code already exists")

        cursor.execute(
            """
            INSERT INTO treatments
            (project_id, treatment_code, treatment_name, description, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                payload.project_id,
                payload.treatment_code,
                payload.treatment_name,
                payload.description,
                payload.status,
                current_user["id"],
            ),
        )

        db.commit()

        return {
            "message": "Treatment created",
            "treatment_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{treatment_id}")
def update_treatment(
    treatment_id: int,
    payload: TreatmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, project_id
            FROM treatments
            WHERE id=%s AND created_by=%s
            """,
            (treatment_id, current_user["id"]),
        )
        treatment = cursor.fetchone()

        if not treatment:
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own treatment"
            )

        cursor.execute(
            """
            SELECT id FROM treatments
            WHERE project_id=%s AND treatment_code=%s AND id != %s
            """,
            (
                treatment["project_id"],
                payload.treatment_code,
                treatment_id,
            ),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Treatment code already exists")

        cursor.execute(
            """
            UPDATE treatments
            SET treatment_code=%s,
                treatment_name=%s,
                description=%s,
                status=%s
            WHERE id=%s
            """,
            (
                payload.treatment_code,
                payload.treatment_name,
                payload.description,
                payload.status,
                treatment_id,
            ),
        )

        db.commit()

        return {
            "message": "Treatment updated",
            "treatment_id": treatment_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{treatment_id}")
def delete_treatment(
    treatment_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM treatments
            WHERE id=%s AND created_by=%s
            """,
            (treatment_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own treatment"
            )

        cursor.execute(
            "DELETE FROM treatments WHERE id=%s",
            (treatment_id,),
        )

        db.commit()

        return {
            "message": "Treatment deleted",
            "treatment_id": treatment_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()