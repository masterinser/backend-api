from fastapi import APIRouter, Depends

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("")
def get_dashboard(
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        is_admin = has_permission(current_user["id"], "view_all_projects")

        if is_admin:
            cursor.execute("SELECT COUNT(*) AS total FROM projects")
            projects = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM trials")
            trials = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM plots")
            plots = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM observations")
            observations = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM measurements")
            measurements = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM users")
            users = cursor.fetchone()["total"]

        else:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM projects WHERE created_by=%s",
                (current_user["id"],),
            )
            projects = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM trials t
                JOIN projects p ON p.id=t.project_id
                WHERE p.created_by=%s
            """, (current_user["id"],))
            trials = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM plots pl
                JOIN trials t ON t.id=pl.trial_id
                JOIN projects p ON p.id=t.project_id
                WHERE p.created_by=%s
            """, (current_user["id"],))
            plots = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM observations o
                JOIN trials t ON t.id=o.trial_id
                JOIN projects p ON p.id=t.project_id
                WHERE p.created_by=%s
            """, (current_user["id"],))
            observations = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM measurements m
                JOIN observations o ON o.id=m.observation_id
                JOIN trials t ON t.id=o.trial_id
                JOIN projects p ON p.id=t.project_id
                WHERE p.created_by=%s
            """, (current_user["id"],))
            measurements = cursor.fetchone()["total"]

            users = None

        return {
            "projects": projects,
            "trials": trials,
            "plots": plots,
            "observations": observations,
            "measurements": measurements,
            "users": users,
        }

    finally:
        cursor.close()
        db.close()