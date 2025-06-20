import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import timedelta, datetime, timezone

# Adjust imports based on your project structure
# Assuming 'gitwrite_api' is a top-level package or accessible in PYTHONPATH
from gitwrite_api.main import app # Import your FastAPI app
from gitwrite_api.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
    SECRET_KEY,
    ALGORITHM,
    # ACCESS_TOKEN_EXPIRE_MINUTES, # Not directly used in tests, but influences token creation
    get_current_active_user, # To test this dependency
    FAKE_USERS_DB # Import for direct manipulation in one test
)
from gitwrite_api.models import User
# The FAKE_USERS_DB is in security.py, it will be used by the /token endpoint implicitly

client = TestClient(app)

# --- Tests for security.py utilities ---

def test_password_hashing():
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)

def test_create_access_token():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == data["sub"]
    assert "exp" in payload

def test_create_access_token_custom_expiry():
    data = {"sub": "testuser_custom_expiry"}
    custom_delta = timedelta(minutes=5)
    token = create_access_token(data, expires_delta=custom_delta)
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == data["sub"]
    assert "exp" in payload

def test_decode_access_token():
    data = {"sub": "testuser_decode"}
    token = create_access_token(data)
    decoded_payload = decode_access_token(token)
    assert decoded_payload is not None
    assert decoded_payload["sub"] == data["sub"]

def test_decode_invalid_token():
    invalid_token = "this.is.an.invalid.token"
    decoded_payload = decode_access_token(invalid_token)
    assert decoded_payload is None

def test_decode_expired_token():
    expired_delta = timedelta(seconds=-1) # Token expired 1 second ago
    data = {"sub": "testuser_expired"}

    # Create an already expired token
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expired_delta
    to_encode.update({"exp": expire})
    expired_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    decoded_payload = decode_access_token(expired_token)
    assert decoded_payload is None # Should fail decoding due to expiry

# --- Tests for /token endpoint ---

def test_login_for_access_token_success():
    # Uses the 'johndoe' user created in FAKE_USERS_DB in security.py
    response = client.post(
        "/token", data={"username": "johndoe", "password": "secret"}
    )
    assert response.status_code == 200, response.text
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    payload = decode_access_token(token_data["access_token"])
    assert payload is not None
    assert payload["sub"] == "johndoe"

def test_login_for_access_token_failure_wrong_password():
    response = client.post(
        "/token", data={"username": "johndoe", "password": "wrongpassword"}
    )
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Incorrect username or password"

def test_login_for_access_token_failure_wrong_username():
    response = client.post(
        "/token", data={"username": "nonexistentuser", "password": "secret"}
    )
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Incorrect username or password"

# --- Tests for get_current_active_user dependency ---

# Need a dummy endpoint that uses the dependency.
# Adding it directly to the app instance for testing.
# This is generally fine for TestClient usage.
@app.get("/test-users/me", response_model=User, tags=["test"])
async def read_test_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# Re-initialize client if app routes were added after client was created
# This ensures the new /test-users/me route is picked up.
# However, FastAPI TestClient usually handles this dynamically if app instance is modified.
# client = TestClient(app) # Uncomment if tests fail to find the new route

def test_get_current_active_user_valid_token():
    login_response = client.post("/token", data={"username": "johndoe", "password": "secret"})
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    user_response = client.get("/test-users/me", headers=headers)
    assert user_response.status_code == 200, user_response.text
    user_data = user_response.json()
    assert user_data["username"] == "johndoe"
    assert not user_data.get("disabled", False) # Check disabled status, default to False if not present

def test_get_current_active_user_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/test-users/me", headers=headers)
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Could not validate credentials"

def test_get_current_active_user_disabled_user():
    # Add a temporary disabled user
    original_disabled_user_state = FAKE_USERS_DB.get("disabled_user_for_test")
    FAKE_USERS_DB["disabled_user_for_test"] = {
        "username": "disabled_user_for_test",
        "full_name": "Disabled Test User",
        "email": "disabled_test@example.com",
        "hashed_password": get_password_hash("test"),
        "disabled": True,
    }

    try:
        login_response = client.post("/token", data={"username": "disabled_user_for_test", "password": "test"})
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/test-users/me", headers=headers)
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Inactive user"
    finally:
        # Clean up: remove or restore the disabled user
        if original_disabled_user_state is None:
            if "disabled_user_for_test" in FAKE_USERS_DB:
                del FAKE_USERS_DB["disabled_user_for_test"]
        else:
            FAKE_USERS_DB["disabled_user_for_test"] = original_disabled_user_state
