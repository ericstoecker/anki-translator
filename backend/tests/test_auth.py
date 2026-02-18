import pytest
from app.auth import create_access_token, decode_token, hash_password, verify_password


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed)
        assert not verify_password("wrong", hashed)

    def test_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token("user-123")
        user_id = decode_token(token)
        assert user_id == "user-123"

    def test_invalid_token(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            decode_token("invalid.token.here")


class TestAuthEndpoints:
    async def test_login_success(self, client, test_user):
        resp = await client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, test_user):
        resp = await client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/auth/login", json={
            "username": "nobody",
            "password": "test",
        })
        assert resp.status_code == 401

    async def test_me_authenticated(self, client, test_user, auth_headers):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    async def test_me_unauthenticated(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)  # no bearer token
