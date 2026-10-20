from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository


def test_register_login_and_read_current_user(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "founder@example.com",
            "password": "Password1",
            "full_name": "Bazart Founder",
        },
    )
    assert register_response.status_code == 201
    user = register_response.json()
    assert user["email"] == "founder@example.com"
    assert "hashed_password" not in user

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "founder@example.com", "password": "Password1"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "founder@example.com"


def test_protected_endpoint_requires_access_token(client: TestClient) -> None:
    unauthorized_response = client.get("/api/v1/auth/me")
    assert unauthorized_response.status_code == 401

    client.post(
        "/api/v1/auth/register",
        json={"email": "protected@example.com", "password": "Password1"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "protected@example.com", "password": "Password1"},
    )
    token = login_response.json()["access_token"]

    protected_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert protected_response.status_code == 200


def test_admin_only_endpoint(client: TestClient, db_session: Session) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "password": "Password1"},
    )
    user_repository = UserRepository(db_session)
    admin_user = user_repository.get_by_email("admin@example.com")
    assert admin_user is not None
    user_repository.set_role(admin_user, UserRole.ADMIN)

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@example.com", "password": "Password1"},
    )
    token = login_response.json()["access_token"]

    admin_response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert admin_response.status_code == 200


def test_register_duplicate_email_returns_conflict(client: TestClient) -> None:
    payload = {"email": "duplicate@example.com", "password": "Password1"}

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_password_reset_and_email_verification_skeletons(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "Password1"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "verify@example.com", "password": "Password1"},
    )
    access_token = login_response.json()["access_token"]

    forgot_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "verify@example.com"},
    )
    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "Newpass1"},
    )
    assert reset_response.status_code == 200

    verification_token_response = client.post(
        "/api/v1/auth/verification-token",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert verification_token_response.status_code == 200

    verify_response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token_response.json()["verification_token"]},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["is_verified"] is True
