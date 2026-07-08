from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/project-members",
    tags=["Project Members"]
)


class ProjectMemberCreate(BaseModel):
    project_id: int
    user_id: int
    member_role: str | None = None


@router.get("")
def get_project_members(
    project_id: int,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT
                    pm.id,
                    pm.project_id,
                    pm.user_id,
                    pm.member_role,
                    pm.created_at,
                    u.username,
                    u.email
                FROM project_members pm
                JOIN users u ON u.id = pm.user_id
                WHERE pm.project_id=%s
                ORDER BY pm.id DESC
            """, (project_id,))
        else:
            cursor.execute("""
                SELECT
                    pm.id,
                    pm.project_id,
                    pm.user_id,
                    pm.member_role,
                    pm.created_at,
                    u.username,
                    u.email
                FROM project_members pm
                JOIN users u ON u.id = pm.user_id
                JOIN projects p ON p.id = pm.project_id
                WHERE pm.project_id=%s
                AND p.created_by=%s
                ORDER BY pm.id DESC
            """, (project_id, current_user["id"]))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_project_member(
    payload: ProjectMemberCreate,
    current_user: dict = Depends(require_permission("manage_projects")),
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
                WHERE id=%s AND created_by=%s
                """,
                (payload.project_id, current_user["id"]),
            )

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")

        cursor.execute(
            "SELECT id FROM users WHERE id=%s",
            (payload.user_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            SELECT id
            FROM project_members
            WHERE project_id=%s AND user_id=%s
        """, (payload.project_id, payload.user_id))

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="User already in this project"
            )

        cursor.execute("""
            INSERT INTO project_members
            (project_id, user_id, member_role)
            VALUES (%s, %s, %s)
        """, (
            payload.project_id,
            payload.user_id,
            payload.member_role,
        ))

        db.commit()

        return {
            "message": "Project member added",
            "member_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{member_id}")
def delete_project_member(
    member_id: int,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT id
                FROM project_members
                WHERE id=%s
            """, (member_id,))
        else:
            cursor.execute("""
                SELECT pm.id
                FROM project_members pm
                JOIN projects p ON p.id = pm.project_id
                WHERE pm.id=%s
                AND p.created_by=%s
            """, (member_id, current_user["id"]))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only members in your own project"
            )

        cursor.execute(
            "DELETE FROM project_members WHERE id=%s",
            (member_id,),
        )

        db.commit()

        return {
            "message": "Project member deleted",
            "member_id": member_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()