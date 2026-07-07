from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, get_current_user


router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)


class ProjectCreate(BaseModel):
    project_name: str
    description: str | None = None
    status: int = 1


class ProjectUpdate(BaseModel):
    project_name: str
    description: str | None = None
    status: int = 1


@router.get("")
def get_projects(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                project_name,
                description,
                status,
                created_by,
                created_at,
                updated_at
            FROM projects
            ORDER BY id DESC
        """)
        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                project_name,
                description,
                status,
                created_by,
                created_at,
                updated_at
            FROM projects
            WHERE id=%s
        """, (project_id,))

        project = cursor.fetchone()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return project

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            INSERT INTO projects
            (project_name, description, status, created_by)
            VALUES (%s, %s, %s, %s)
        """, (
            payload.project_name,
            payload.description,
            payload.status,
            current_user["id"],
        ))

        db.commit()

        return {
            "message": "Project created",
            "project_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM projects WHERE id=%s AND created_by=%s",
            (project_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own project"
            )

        cursor.execute("""
            UPDATE projects
            SET project_name=%s,
                description=%s,
                status=%s
            WHERE id=%s
        """, (
            payload.project_name,
            payload.description,
            payload.status,
            project_id,
        ))

        db.commit()

        return {
            "message": "Project updated",
            "project_id": project_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM projects WHERE id=%s AND created_by=%s",
            (project_id, current_user["id"]),
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own project"
            )

        cursor.execute(
            "DELETE FROM projects WHERE id=%s",
            (project_id,),
        )

        db.commit()

        return {
            "message": "Project deleted",
            "project_id": project_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()