from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date

from main import get_db, get_current_user


router = APIRouter(
    prefix="/observations",
    tags=["Observations"]
)


class ObservationCreate(BaseModel):
    trial_id: int
    observation_name: str
    observation_code: str
    unit: str | None = None
    daa: int | None = None
    observation_date: date | None = None
    note: str | None = None
    status: int = 1


class ObservationUpdate(BaseModel):
    observation_name: str
    observation_code: str
    unit: str | None = None
    daa: int | None = None
    observation_date: date | None = None
    note: str | None = None
    status: int = 1


@router.get("")
def get_observations(
    trial_id: int | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if trial_id:
            cursor.execute(
                """
                SELECT *
                FROM observations
                WHERE trial_id=%s
                ORDER BY id DESC
                """,
                (trial_id,),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM observations
                ORDER BY id DESC
                """
            )

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_observation(
    payload: ObservationCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM trials WHERE id=%s",
            (payload.trial_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Trial not found")

        cursor.execute(
            """
            INSERT INTO observations
            (
                trial_id,
                observation_name,
                observation_code,
                unit,
                daa,
                observation_date,
                note,
                status,
                created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.trial_id,
                payload.observation_name,
                payload.observation_code,
                payload.unit,
                payload.daa,
                payload.observation_date,
                payload.note,
                payload.status,
                current_user["id"],
            ),
        )

        db.commit()

        return {
            "message": "Observation created",
            "observation_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{observation_id}")
def update_observation(
    observation_id: int,
    payload: ObservationUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM observations
            WHERE id=%s AND created_by=%s
            """,
            (observation_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own observation"
            )

        cursor.execute(
            """
            UPDATE observations
            SET observation_name=%s,
                observation_code=%s,
                unit=%s,
                daa=%s,
                observation_date=%s,
                note=%s,
                status=%s
            WHERE id=%s
            """,
            (
                payload.observation_name,
                payload.observation_code,
                payload.unit,
                payload.daa,
                payload.observation_date,
                payload.note,
                payload.status,
                observation_id,
            ),
        )

        db.commit()

        return {
            "message": "Observation updated",
            "observation_id": observation_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{observation_id}")
def delete_observation(
    observation_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM observations
            WHERE id=%s AND created_by=%s
            """,
            (observation_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own observation"
            )

        cursor.execute(
            "DELETE FROM observations WHERE id=%s",
            (observation_id,),
        )

        db.commit()

        return {
            "message": "Observation deleted",
            "observation_id": observation_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()