# routers/weedy_rice.py

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, get_current_user


router = APIRouter(
    prefix="/weedy-rice",
    tags=["Weedy Rice"]
)


class WeedyRiceRow(BaseModel):
    plot_no: int
    values: list[float | None]


class WeedyRiceCreate(BaseModel):
    location: str = "Weedy rice"
    daa: int
    record_date: date
    note: str | None = None
    rows: list[WeedyRiceRow]


@router.post("/records")
def create_weedy_rice_record(
    payload: WeedyRiceCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            INSERT INTO weedy_rice_records
            (location, daa, record_date, note, created_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                payload.location,
                payload.daa,
                payload.record_date,
                payload.note,
                current_user["id"],
            ),
        )

        record_id = cursor.lastrowid

        for row in payload.rows:
            for index, height in enumerate(row.values, start=1):
                cursor.execute(
                    """
                    INSERT INTO weedy_rice_heights
                    (record_id, plot_no, plant_no, height_cm, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        record_id,
                        row.plot_no,
                        index,
                        height,
                        current_user["id"],
                    ),
                )

        db.commit()

        return {
            "message": "Weedy rice record created",
            "record_id": record_id,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.get("/records/{record_id}")
def get_weedy_rice_record(
    record_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT *
            FROM weedy_rice_records
            WHERE id=%s
            """,
            (record_id,),
        )

        record = cursor.fetchone()

        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        cursor.execute(
            """
            SELECT plot_no, plant_no, height_cm
            FROM weedy_rice_heights
            WHERE record_id=%s
            ORDER BY plot_no ASC, plant_no ASC
            """,
            (record_id,),
        )

        heights = cursor.fetchall()

        rows_dict = {}

        for item in heights:
            plot_no = item["plot_no"]

            if plot_no not in rows_dict:
                rows_dict[plot_no] = {
                    "plot_no": plot_no,
                    "values": []
                }

            rows_dict[plot_no]["values"].append(
                float(item["height_cm"]) if item["height_cm"] is not None else None
            )

        return {
            "record": record,
            "rows": list(rows_dict.values()),
        }

    finally:
        cursor.close()
        db.close()


@router.put("/records/{record_id}")
def update_weedy_rice_record(
    record_id: int,
    payload: WeedyRiceCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id FROM weedy_rice_records
            WHERE id=%s AND created_by=%s
            """,
            (record_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own record"
            )

        cursor.execute(
            """
            UPDATE weedy_rice_records
            SET location=%s, daa=%s, record_date=%s, note=%s
            WHERE id=%s
            """,
            (
                payload.location,
                payload.daa,
                payload.record_date,
                payload.note,
                record_id,
            ),
        )

        cursor.execute(
            "DELETE FROM weedy_rice_heights WHERE record_id=%s",
            (record_id,),
        )

        for row in payload.rows:
            for index, height in enumerate(row.values, start=1):
                cursor.execute(
                    """
                    INSERT INTO weedy_rice_heights
                    (record_id, plot_no, plant_no, height_cm, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        record_id,
                        row.plot_no,
                        index,
                        height,
                        current_user["id"],
                    ),
                )

        db.commit()

        return {
            "message": "Weedy rice record updated",
            "record_id": record_id,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()

@router.delete("/records/{record_id}")
def delete_weedy_rice_record(
    record_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id FROM weedy_rice_records
            WHERE id=%s AND created_by=%s
            """,
            (record_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own record"
            )

        cursor.execute(
            "DELETE FROM weedy_rice_records WHERE id=%s",
            (record_id,),
        )

        db.commit()

        return {
            "message": "Weedy rice record deleted",
            "record_id": record_id,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()
        

@router.get("/template")
def get_weedy_rice_template(
    start_plot: int = 101,
    end_plot: int = 140,
    plants: int = 10,
    current_user: dict = Depends(get_current_user),
):
    rows = []

    for plot_no in range(start_plot, end_plot + 1):
        rows.append({
            "plot_no": plot_no,
            "values": [None for _ in range(plants)]
        })

    return {
        "location": "Weedy rice",
        "daa": 60,
        "record_date": date.today(),
        "note": "",
        "rows": rows
    }