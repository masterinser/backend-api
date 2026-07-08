from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/trials",
    tags=["Trials"]
)


class TrialCreate(BaseModel):
    project_id: int
    trial_name: str
    location: str | None = None
    season: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: int = 1


class TrialUpdate(BaseModel):
    trial_name: str
    location: str | None = None
    season: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: int = 1


@router.get("")
def get_trials(
    project_id: int | None = None,
    current_user: dict = Depends(require_permission("manage_trials")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            if project_id:
                cursor.execute(
                    """
                    SELECT *
                    FROM trials
                    WHERE project_id=%s
                    ORDER BY id DESC
                    """,
                    (project_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM trials
                    ORDER BY id DESC
                    """
                )
        else:
            if project_id:
                cursor.execute(
                    """
                    SELECT t.*
                    FROM trials t
                    INNER JOIN projects p ON p.id=t.project_id
                    WHERE t.project_id=%s
                    AND p.created_by=%s
                    ORDER BY t.id DESC
                    """,
                    (project_id, current_user["id"]),
                )
            else:
                cursor.execute(
                    """
                    SELECT t.*
                    FROM trials t
                    INNER JOIN projects p ON p.id=t.project_id
                    WHERE p.created_by=%s
                    ORDER BY t.id DESC
                    """,
                    (current_user["id"],),
                )

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.get("/{trial_id}")
def get_trial(
    trial_id: int,
    current_user: dict = Depends(require_permission("manage_trials")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute(
                """
                SELECT *
                FROM trials
                WHERE id=%s
                """,
                (trial_id,),
            )
        else:
            cursor.execute(
                """
                SELECT t.*
                FROM trials t
                INNER JOIN projects p ON p.id=t.project_id
                WHERE t.id=%s
                AND p.created_by=%s
                """,
                (trial_id, current_user["id"]),
            )

        data = cursor.fetchone()

        if not data:
            raise HTTPException(status_code=404, detail="Trial not found")

        return data

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_trial(
    payload: TrialCreate,
    current_user: dict = Depends(require_permission("manage_trials")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute(
                "SELECT id FROM projects WHERE id=%s",
                (payload.project_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id
                FROM projects
                WHERE id=%s
                AND created_by=%s
                """,
                (payload.project_id, current_user["id"]),
            )

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")

        cursor.execute(
            """
            INSERT INTO trials
            (
                project_id,
                trial_name,
                location,
                season,
                start_date,
                end_date,
                status,
                created_by
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                payload.project_id,
                payload.trial_name,
                payload.location,
                payload.season,
                payload.start_date,
                payload.end_date,
                payload.status,
                current_user["id"],
            ),
        )

        db.commit()

        return {
            "message": "Trial created",
            "trial_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{trial_id}")
def update_trial(
    trial_id: int,
    payload: TrialUpdate,
    current_user: dict = Depends(require_permission("manage_trials")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute(
                """
                SELECT id
                FROM trials
                WHERE id=%s
                """,
                (trial_id,),
            )
        else:
            cursor.execute(
                """
                SELECT t.id
                FROM trials t
                INNER JOIN projects p ON p.id=t.project_id
                WHERE t.id=%s
                AND p.created_by=%s
                """,
                (trial_id, current_user["id"]),
            )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own trial"
            )

        cursor.execute(
            """
            UPDATE trials
            SET trial_name=%s,
                location=%s,
                season=%s,
                start_date=%s,
                end_date=%s,
                status=%s
            WHERE id=%s
            """,
            (
                payload.trial_name,
                payload.location,
                payload.season,
                payload.start_date,
                payload.end_date,
                payload.status,
                trial_id,
            ),
        )

        db.commit()

        return {
            "message": "Trial updated",
            "trial_id": trial_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{trial_id}")
def delete_trial(
    trial_id: int,
    current_user: dict = Depends(require_permission("manage_trials")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute(
                """
                SELECT id
                FROM trials
                WHERE id=%s
                """,
                (trial_id,),
            )
        else:
            cursor.execute(
                """
                SELECT t.id
                FROM trials t
                INNER JOIN projects p ON p.id=t.project_id
                WHERE t.id=%s
                AND p.created_by=%s
                """,
                (trial_id, current_user["id"]),
            )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own trial"
            )

        cursor.execute(
            "DELETE FROM trials WHERE id=%s",
            (trial_id,),
        )

        db.commit()

        return {
            "message": "Trial deleted",
            "trial_id": trial_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()