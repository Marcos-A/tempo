"""Reusable request dependencies shared by route modules."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    """Return the logged-in admin or redirect to the login page.

    The admin area uses a signed session cookie instead of a separate auth service,
    which keeps the MVP simple while still blocking anonymous access.
    """

    admin_id = request.session.get("admin_user_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})

    user = db.get(AdminUser, admin_id)
    if not user:
        # If the session references a user that no longer exists, clear it so
        # the browser is not stuck with a broken authenticated state.
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    return user
