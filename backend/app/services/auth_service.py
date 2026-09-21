from uuid import uuid4

from fastapi import HTTPException

from app.repositories import Database
from app.schemas import UserCreate, UserLogin


class AuthService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def register(self, user_input: UserCreate) -> dict:
        try:
            return self.database.create_user({"id": str(uuid4()), **user_input.model_dump()})
        except Exception as error:
            if "UNIQUE" in str(error).upper():
                raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.") from error
            raise

    def login(self, user_input: UserLogin) -> dict:
        user = self.database.authenticate_user(user_input.email, user_input.password)
        if user is None:
            raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
        return user
