import os

os.environ["MODE"] = "DEV"
os.environ["DOCS_USER"] = "valid_user"
os.environ["DOCS_PASSWORD"] = "valid_password"
os.environ["DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_basic_login_seed_user():
    with client:
        response = client.get("/login", auth=("user", "userpass"))
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome, user!"


def test_jwt_login_and_protected_resource():
    with client:
        login_response = client.post(
            "/login",
            json={"username": "admin", "password": "adminpass"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        protected_response = client.get(
            "/protected_resource",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert protected_response.status_code == 200
    assert protected_response.json()["message"] == "Access granted"


def test_todo_crud():
    with client:
        created = client.post(
            "/todos",
            json={"title": "Buy groceries", "description": "Milk, eggs, bread"},
        )
        assert created.status_code == 201
        todo_id = created.json()["id"]

        read = client.get(f"/todos/{todo_id}")
        assert read.status_code == 200

        updated = client.put(
            f"/todos/{todo_id}",
            json={
                "title": "Buy groceries",
                "description": "Milk, eggs, bread, cheese",
                "completed": True,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["completed"] is True

        deleted = client.delete(f"/todos/{todo_id}")
        assert deleted.status_code == 200
