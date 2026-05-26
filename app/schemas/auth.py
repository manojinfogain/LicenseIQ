from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    role: str
    name: str
    ini: str
    dept: str
    email: str
    staffid: str  # Aspire EMP_STAFFID, used for scoped dashboard calls
    role_source: str = "manual"  # "manual" | "aspire_auto"
