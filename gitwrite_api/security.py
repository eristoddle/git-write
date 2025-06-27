from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt # Already imported
from passlib.context import CryptContext # Already imported

from .models import User, TokenData, UserInDB # Assuming models.py is in the same directory

# TODO: Configure these via environment variables
SECRET_KEY = "your-secret-key"  # This should be a strong, randomly generated key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token") # Adjusted tokenUrl to be relative

# This is a placeholder for user database.
# In a real application, this would query a database.
from .models import UserRole # Import UserRole

FAKE_USERS_DB = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$2b$12$m/Oxd60KIDPOcd8Kq.t4Eutw6xl91AvdKD7DbtKJCECo4yg9Z9eMS", # Hash a default password
        "disabled": False,
        "roles": [UserRole.OWNER],  # Assign OWNER role
    },
    "editoruser": {
        "username": "editoruser",
        "full_name": "Editor User",
        "email": "editor@example.com",
        "hashed_password": get_password_hash("editpass"),
        "disabled": False,
        "roles": [UserRole.EDITOR],
    },
    "writeruser": {
        "username": "writeruser",
        "full_name": "Writer User",
        "email": "writer@example.com",
        "hashed_password": get_password_hash("writepass"),
        "disabled": False,
        "roles": [UserRole.WRITER],
    },
    "betauser": {
        "username": "betauser",
        "full_name": "Beta Reader User",
        "email": "beta@example.com",
        "hashed_password": get_password_hash("betapass"),
        "disabled": False,
        "roles": [UserRole.BETA_READER],
    }
}

def get_user(db, username: str) -> Optional[UserInDB]:
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    token_data = TokenData(username=username)

    user = get_user(FAKE_USERS_DB, username=token_data.username)
    # Return User model for API responses, but internally we might have UserInDB
    if user is None:
        raise credentials_exception
    # Convert UserInDB to User before returning if necessary,
    # but Pydantic handles inheritance well for response models.
    # For dependency injection, returning UserInDB is fine if functions expect User.
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def require_role(required_roles: list[UserRole]):
    """
    Dependency that checks if the current user has at least one of the required roles.
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned roles.",
            )

        has_required_role = any(role in current_user.roles for role in required_roles)

        if not has_required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have the required role(s): {', '.join(role.value for role in required_roles)}",
            )
        return current_user
    return role_checker
