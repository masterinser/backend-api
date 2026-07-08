from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from main import get_db, require_permission, has_permission


router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


class ProductCreate(BaseModel):
    product_name: str
    active_ingredient: str | None = None
    product_type: str | None = None
    description: str | None = None
    status: int = 1


class ProductUpdate(BaseModel):
    product_name: str
    active_ingredient: str | None = None
    product_type: str | None = None
    description: str | None = None
    status: int = 1


@router.get("")
def get_products(
    product_type: str | None = None,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            if product_type:
                cursor.execute("""
                    SELECT *
                    FROM products
                    WHERE product_type=%s
                    ORDER BY product_name ASC
                """, (product_type,))
            else:
                cursor.execute("""
                    SELECT *
                    FROM products
                    ORDER BY product_name ASC
                """)
        else:
            if product_type:
                cursor.execute("""
                    SELECT *
                    FROM products
                    WHERE product_type=%s
                    AND created_by=%s
                    ORDER BY product_name ASC
                """, (product_type, current_user["id"]))
            else:
                cursor.execute("""
                    SELECT *
                    FROM products
                    WHERE created_by=%s
                    ORDER BY product_name ASC
                """, (current_user["id"],))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@router.post("")
def create_product(
    payload: ProductCreate,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id
            FROM products
            WHERE product_name=%s
            AND created_by=%s
        """, (payload.product_name, current_user["id"]))

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Product already exists"
            )

        cursor.execute("""
            INSERT INTO products
            (
                product_name,
                active_ingredient,
                product_type,
                description,
                status,
                created_by
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            payload.product_name,
            payload.active_ingredient,
            payload.product_type,
            payload.description,
            payload.status,
            current_user["id"],
        ))

        db.commit()

        return {
            "message": "Product created",
            "product_id": cursor.lastrowid
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.put("/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT id
                FROM products
                WHERE id=%s
            """, (product_id,))
        else:
            cursor.execute("""
                SELECT id
                FROM products
                WHERE id=%s
                AND created_by=%s
            """, (product_id, current_user["id"]))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own product"
            )

        cursor.execute("""
            UPDATE products
            SET
                product_name=%s,
                active_ingredient=%s,
                product_type=%s,
                description=%s,
                status=%s
            WHERE id=%s
        """, (
            payload.product_name,
            payload.active_ingredient,
            payload.product_type,
            payload.description,
            payload.status,
            product_id,
        ))

        db.commit()

        return {
            "message": "Product updated",
            "product_id": product_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_user: dict = Depends(require_permission("manage_projects")),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if has_permission(current_user["id"], "view_all_projects"):
            cursor.execute("""
                SELECT id
                FROM products
                WHERE id=%s
            """, (product_id,))
        else:
            cursor.execute("""
                SELECT id
                FROM products
                WHERE id=%s
                AND created_by=%s
            """, (product_id, current_user["id"]))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own product"
            )

        cursor.execute(
            "DELETE FROM products WHERE id=%s",
            (product_id,),
        )

        db.commit()

        return {
            "message": "Product deleted",
            "product_id": product_id
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()