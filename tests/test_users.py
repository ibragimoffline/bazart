import pytest
from conftest import AuthenticatedUser
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("unverified_phones")
def test_user_can_read_and_update_profile(
    client: TestClient,
    test_user: AuthenticatedUser,
) -> None:
    read_response = client.get("/api/v1/users/me", headers=test_user.headers)
    assert read_response.status_code == 200
    profile = read_response.json()
    assert profile["email"] == test_user.email
    assert profile["phone"] is None

    update_response = client.patch(
        "/api/v1/users/me",
        headers=test_user.headers,
        json={
            "full_name": "Updated User",
            "phone": "+998901234567",
            "location": "Tashkent",
        },
    )
    assert update_response.status_code == 200
    updated_profile = update_response.json()
    assert updated_profile["full_name"] == "Updated User"
    assert updated_profile["phone"] == "+998901234567"
    assert updated_profile["location"] == "Tashkent"
