"""Creates a super admin, or promotes an existing user. Deliberately only possible from the server.

  docker compose exec -e SUPERADMIN_PASSWORD=... api python -m scripts.make_superadmin owner owner@example.com
"""
import asyncio
import os
import sys
from datetime import date

from app import models  # noqa: F401
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.users import repository as users
from app.modules.users.models import Profile, User


async def main(username: str, email: str | None) -> None:
    async with SessionLocal() as s:
        user = await users.by_username(s, username)
        if user is None:
            password = os.environ.get("SUPERADMIN_PASSWORD", "")
            if not email or len(password) < 12:
                raise SystemExit("A new account needs an email argument and SUPERADMIN_PASSWORD of at least 12 characters")
            user = User(
                username=username, email=email, password_hash=hash_password(password), status="active",
                date_of_birth=date(1990, 1, 1),
            )
            await users.add_user(s, user, Profile(display_name=username))
        user.role = "superadmin"
        await users.audit(s, None, "admin.superadmin_granted", str(user.id), None, {"via": "server command"})
        await s.commit()
    print(f"{username} is now a super admin")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
