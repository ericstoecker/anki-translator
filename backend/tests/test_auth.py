class TestAuthEndpoints:
    async def test_given_valid_credentials_when_login_then_returns_token(
        self, client, test_user
    ):
        resp = await client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_given_wrong_password_when_login_then_returns_401(
        self, client, test_user
    ):
        resp = await client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_given_nonexistent_user_when_login_then_returns_401(self, client):
        resp = await client.post(
            "/auth/login",
            json={"username": "nobody", "password": "test"},
        )
        assert resp.status_code == 401

    async def test_given_authenticated_when_get_me_then_returns_user(
        self, client, auth_headers
    ):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    async def test_given_no_token_when_get_me_then_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)

    async def test_when_update_native_language_then_persists(
        self, client, auth_headers
    ):
        resp = await client.patch(
            "/auth/me?native_language=French", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["native_language"] == "French"

        # Verify via GET
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.json()["native_language"] == "French"
