from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, get_current_user


router = APIRouter(
    prefix="/plots",
    tags=["Plots"]
)


class PlotCreate(BaseModel):
    trial_id: int
    plot_no: str
    rep: int | None = None
    treatment: str | None = None
    variety: str | None = None
    note: str | None = None
    status: int = 1


class PlotUpdate(BaseModel):
    plot_no: str
    rep: int | None = None
    treatment: str | None = None
    variety: str | None = None
    note: str | None = None
    status: int = 1


@router.get("")
def get_plots(
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
                FROM plots
                WHERE trial_id=%s
                ORDER BY id ASC
                """,
                (trial_id,),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM plots
                ORDER BY id DESC
                """
            )

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_plot(
    payload: PlotCreate,
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
            SELECT id FROM plots
            WHERE trial_id=%s AND plot_no=%s
            """,
            (payload.trial_id, payload.plot_no),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Plot already exists in this trial")

        cursor.execute(
            """
            INSERT INTO plots
            (trial_id, plot_no, rep, treatment, variety, note, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.trial_id,
                payload.plot_no,
                payload.rep,
                payload.treatment,
                payload.variety,
                payload.note,
                payload.status,
                current_user["id"],
            ),
        )

        db.commit()

        return {
            "message": "Plot created",
            "plot_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{plot_id}")
def update_plot(
    plot_id: int,
    payload: PlotUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, trial_id
            FROM plots
            WHERE id=%s AND created_by=%s
            """,
            (plot_id, current_user["id"]),
        )
        plot = cursor.fetchone()

        if not plot:
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own plot"
            )

        cursor.execute(
            """
            SELECT id FROM plots
            WHERE trial_id=%s AND plot_no=%s AND id != %s
            """,
            (plot["trial_id"], payload.plot_no, plot_id),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Plot already exists in this trial")

        cursor.execute(
            """
            UPDATE plots
            SET plot_no=%s,
                rep=%s,
                treatment=%s,
                variety=%s,
                note=%s,
                status=%s
            WHERE id=%s
            """,
            (
                payload.plot_no,
                payload.rep,
                payload.treatment,
                payload.variety,
                payload.note,
                payload.status,
                plot_id,
            ),
        )

        db.commit()

        return {
            "message": "Plot updated",
            "plot_id": plot_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{plot_id}")
def delete_plot(
    plot_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM plots
            WHERE id=%s AND created_by=%s
            """,
            (plot_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own plot"
            )

        cursor.execute("DELETE FROM plots WHERE id=%s", (plot_id,))
        db.commit()

        return {
            "message": "Plot deleted",
            "plot_id": plot_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()