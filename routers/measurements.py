from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/measurements",
    tags=["Measurements"]
)


class MeasurementRow(BaseModel):
    plot_id: int
    values: list[float | None]


class MeasurementSaveGrid(BaseModel):
    observation_id: int
    rows: list[MeasurementRow]


@router.get("/template")
def get_measurement_template(
    trial_id: int,
    samples: int = 10,
    current_user: dict = Depends(require_permission("manage_measurements")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT id, plot_no, rep, treatment, variety
                FROM plots
                WHERE trial_id=%s
                ORDER BY plot_no ASC
            """, (trial_id,))
        else:
            cursor.execute("""
                SELECT p.id, p.plot_no, p.rep, p.treatment, p.variety
                FROM plots p
                INNER JOIN trials t ON t.id=p.trial_id
                INNER JOIN projects pr ON pr.id=t.project_id
                WHERE p.trial_id=%s
                AND pr.created_by=%s
                ORDER BY p.plot_no ASC
            """, (trial_id, current_user["id"]))

        plots = cursor.fetchall()

        rows = []
        for plot in plots:
            rows.append({
                "plot_id": plot["id"],
                "plot_no": plot["plot_no"],
                "rep": plot["rep"],
                "treatment": plot["treatment"],
                "variety": plot["variety"],
                "values": [None for _ in range(samples)]
            })

        return {
            "trial_id": trial_id,
            "samples": samples,
            "rows": rows
        }

    finally:
        cursor.close()
        db.close()


@router.post("/save-grid")
def save_measurement_grid(
    payload: MeasurementSaveGrid,
    current_user: dict = Depends(require_permission("manage_measurements")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute(
                "SELECT id, trial_id FROM observations WHERE id=%s",
                (payload.observation_id,),
            )
        else:
            cursor.execute("""
                SELECT o.id, o.trial_id
                FROM observations o
                INNER JOIN trials t ON t.id=o.trial_id
                INNER JOIN projects p ON p.id=t.project_id
                WHERE o.id=%s
                AND p.created_by=%s
            """, (payload.observation_id, current_user["id"]))

        observation = cursor.fetchone()

        if not observation:
            raise HTTPException(status_code=404, detail="Observation not found")

        for row in payload.rows:
            if has_permission(current_user["id"], "view_all_projects"):
                cursor.execute("""
                    SELECT id
                    FROM plots
                    WHERE id=%s
                    AND trial_id=%s
                """, (row.plot_id, observation["trial_id"]))
            else:
                cursor.execute("""
                    SELECT pl.id
                    FROM plots pl
                    INNER JOIN trials t ON t.id=pl.trial_id
                    INNER JOIN projects p ON p.id=t.project_id
                    WHERE pl.id=%s
                    AND pl.trial_id=%s
                    AND p.created_by=%s
                """, (
                    row.plot_id,
                    observation["trial_id"],
                    current_user["id"],
                ))

            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Plot id {row.plot_id} not found"
                )

            for index, value in enumerate(row.values, start=1):
                cursor.execute("""
                    INSERT INTO measurements
                    (observation_id, plot_id, sample_no, value_decimal, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        value_decimal=VALUES(value_decimal),
                        updated_at=CURRENT_TIMESTAMP
                """, (
                    payload.observation_id,
                    row.plot_id,
                    index,
                    value,
                    current_user["id"],
                ))

        db.commit()

        return {
            "message": "Measurements saved",
            "observation_id": payload.observation_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.get("/grid")
def get_measurement_grid(
    observation_id: int,
    current_user: dict = Depends(require_permission("manage_measurements")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT
                    o.id AS observation_id,
                    o.trial_id,
                    o.observation_name,
                    o.observation_code,
                    o.unit,
                    o.daa,
                    o.observation_date
                FROM observations o
                WHERE o.id=%s
            """, (observation_id,))
        else:
            cursor.execute("""
                SELECT
                    o.id AS observation_id,
                    o.trial_id,
                    o.observation_name,
                    o.observation_code,
                    o.unit,
                    o.daa,
                    o.observation_date
                FROM observations o
                INNER JOIN trials t ON t.id=o.trial_id
                INNER JOIN projects p ON p.id=t.project_id
                WHERE o.id=%s
                AND p.created_by=%s
            """, (observation_id, current_user["id"]))

        observation = cursor.fetchone()

        if not observation:
            raise HTTPException(status_code=404, detail="Observation not found")

        cursor.execute("""
            SELECT
                p.id AS plot_id,
                p.plot_no,
                p.rep,
                p.treatment,
                p.variety,
                m.sample_no,
                m.value_decimal
            FROM plots p
            LEFT JOIN measurements m
                ON p.id = m.plot_id
                AND m.observation_id = %s
            WHERE p.trial_id=%s
            ORDER BY p.plot_no ASC, m.sample_no ASC
        """, (
            observation_id,
            observation["trial_id"],
        ))

        data = cursor.fetchall()
        rows_dict = {}

        for item in data:
            plot_id = item["plot_id"]

            if plot_id not in rows_dict:
                rows_dict[plot_id] = {
                    "plot_id": plot_id,
                    "plot_no": item["plot_no"],
                    "rep": item["rep"],
                    "treatment": item["treatment"],
                    "variety": item["variety"],
                    "values": []
                }

            if item["sample_no"] is not None:
                rows_dict[plot_id]["values"].append(
                    float(item["value_decimal"]) if item["value_decimal"] is not None else None
                )

        return {
            "observation": observation,
            "rows": list(rows_dict.values())
        }

    finally:
        cursor.close()
        db.close()