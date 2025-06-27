from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

# Assuming security.py and models.py are in the parent directory of routers
# Adjust import paths if your structure is different.
# This structure assumes:
# gitwrite_api/
# ├── main.py
# ├── security.py
# ├── models.py
# └── routers/
#     └── auth.py

# To make relative imports work correctly from within the routers package,
# we might need to adjust how security and models are imported,
# or rely on Python's path resolution if gitwrite_api is in PYTHONPATH.

# Let's try importing from the parent package explicitly for clarity
from ..security import create_access_token, verify_password, get_user, ACCESS_TOKEN_EXPIRE_MINUTES
from ..models import Token # User model might not be directly needed here, but Token is.

router = APIRouter(
    tags=["authentication"], # Add a tag for Swagger UI
)


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    print(f"Attempting login for username: {form_data.username}")
    # In a real app, FAKE_USERS_DB would be a real database session/connection
    from ..security import FAKE_USERS_DB # Import here to avoid circular dependency issues at module load time

    user = get_user(FAKE_USERS_DB, form_data.username)
    if not user:
        print(f"User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User found: {user.username}. Verifying password.")
    password_verified = verify_password(form_data.password, user.hashed_password)

    if not password_verified:
        print(f"Password verification failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"Password verified for user: {form_data.username}. Creating access token.")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
