"""
Authentication service.

Handles password hashing, JWT token generation, and user authentication.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.schemas.auth import TokenPayload

settings = get_settings()

# Password hashing context with bcrypt (12 rounds)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Bcrypt hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: User's UUID as string

    Returns:
        str: Encoded JWT token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.jwt_expiration_hours)

    payload = {
        "sub": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload | None:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**payload)
    except JWTError:
        return None


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """
    Authenticate a user by email and password.

    Args:
        db: Database session
        email: User's email address
        password: Plain text password

    Returns:
        User if authentication successful, None otherwise
    """
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Get a user by email address.

    Args:
        db: Database session
        email: User's email address

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """
    Get a user by ID.

    Args:
        db: Database session
        user_id: User's UUID as string

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        email: User's email address
        password: Plain text password (will be hashed)
        full_name: User's full name

    Returns:
        User: Created user instance
    """
    hashed_password = hash_password(password)

    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
    )

    db.add(user)
    await db.flush()
    await db.refresh(user)

    return user
