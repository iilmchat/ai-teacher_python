"""
Tests for authentication endpoints
"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


def test_register_user(client: TestClient):
    """Test user registration"""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data


def test_register_duplicate_email(client: TestClient):
    """Test registration with duplicate email"""
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "username": "user1",
            "password": "password123"
        }
    )
    
    # Second registration with same email
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "username": "user2",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_register_duplicate_username(client: TestClient):
    """Test registration with duplicate username"""
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user1@example.com",
            "username": "duplicateuser",
            "password": "password123"
        }
    )
    
    # Second registration with same username
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "duplicateuser",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "Username already taken" in response.json()["detail"]


def test_login_success(client: TestClient):
    """Test successful login"""
    # Register user first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "password123"
        }
    )
    
    # Login with username
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "loginuser",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_email(client: TestClient):
    """Test login with email instead of username"""
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "email@example.com",
            "username": "emailuser",
            "password": "password123"
        }
    )
    
    # Login with email
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "email@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client: TestClient):
    """Test login with wrong password"""
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "username": "wrongpassuser",
            "password": "correctpassword"
        }
    )
    
    # Login with wrong password
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "wrongpassuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401


def test_get_me(client: TestClient):
    """Test get current user info"""
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "password123"
        }
    )
    
    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "meuser",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]
    
    # Get current user
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "meuser"


def test_refresh_token(client: TestClient):
    """Test token refresh"""
    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "username": "refreshuser",
            "password": "password123"
        }
    )
    
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "refreshuser",
            "password": "password123"
        }
    )
    refresh_token = login_response.json()["refresh_token"]
    
    # Refresh token
    response = client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_protected_route_without_token(client: TestClient):
    """Test accessing protected route without token"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403
