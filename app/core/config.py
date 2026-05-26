from sqlalchemy.engine import URL

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LicenseIQ API"
    app_env: str = "dev"
    api_v1_str: str = "/api/v1"
    backend_cors_origins: str

    # Database configuration — all required, read from .env
    db_server: str
    db_port: int | None = None
    db_name: str
    db_user: str
    db_password: str
    db_driver: str
    db_trust_server_certificate: bool = True

    # Aspire source database (read-only)
    aspire_db_server: str | None = None
    aspire_db_port: int | None = None
    aspire_db_name: str = "Aspire"
    aspire_db_user: str | None = None
    aspire_db_password: str | None = None
    aspire_db_driver: str | None = None
    aspire_db_trust_server_certificate: bool | None = None

    # Email / Gmail SMTP configuration (Google Workspace App Password)
    email_enabled: bool = False
    email_sender: str | None = None           # e.g. licenseiq@yourdomain.com
    email_app_password: str | None = None     # 16-char Google App Password
    email_admin: str | None = None            # License Admin email address
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587

    # Azure AD SSO (OAuth 2.0 Authorization Code flow via MSAL)
    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_tenant_id: str = ""
    sso_redirect_uri: str = "http://127.0.0.1:8000/auth/callback"
    sso_allowed_emails: str = ""             # comma-separated whitelist
    sso_dev_mode: bool = True                # bypass SSO in local development

    # Starlette session middleware secret key
    session_secret_key: str = "change-me-to-a-random-256-bit-secret-in-production"

    # When true, users without a LicenseIQ role mapping may log in if they hold an
    # Aspire org role (GDL head, account owner, or project manager).
    auth_aspire_auto_role: bool = True

    @property
    def backend_cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return self._build_sqlalchemy_url(database_name=self.db_name)

    @property
    def master_database_url(self) -> str:
        return self._build_sqlalchemy_url(database_name="master")

    @property
    def aspire_database_url(self) -> str:
        return self._build_sqlalchemy_url(
            database_name=self.aspire_db_name,
            server=self.aspire_db_server or self.db_server,
            port=self.aspire_db_port,
            user=self.aspire_db_user or self.db_user,
            password=self.aspire_db_password or self.db_password,
            driver=self.aspire_db_driver or self.db_driver,
            trust_server_certificate=(
                self.aspire_db_trust_server_certificate
                if self.aspire_db_trust_server_certificate is not None
                else self.db_trust_server_certificate
            ),
        )

    def _build_sql_server_host(self, server: str, port: int | None) -> str:
        # Named SQL Server instances commonly use dynamic ports, so do not append
        # a fixed port when the server value already contains an instance name.
        if "\\" in server:
            return server
        if port:
            return f"{server},{port}"
        return server

    def _build_sqlalchemy_url(
        self,
        database_name: str,
        *,
        server: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        driver: str | None = None,
        trust_server_certificate: bool | None = None,
    ) -> str:
        resolved_server = server or self.db_server
        resolved_port = self.db_port if port is None and resolved_server == self.db_server else port
        resolved_user = user or self.db_user
        resolved_password = password or self.db_password
        resolved_driver = driver or self.db_driver
        resolved_trust = self.db_trust_server_certificate if trust_server_certificate is None else trust_server_certificate
        trust = "yes" if resolved_trust else "no"
        odbc_connect = (
            f"DRIVER={{{resolved_driver}}};"
            f"SERVER={self._build_sql_server_host(resolved_server, resolved_port)};"
            f"DATABASE={database_name};"
            f"UID={resolved_user};"
            f"PWD={resolved_password};"
            f"TrustServerCertificate={trust};"
        )
        return str(
            URL.create(
                "mssql+pyodbc",
                query={"odbc_connect": odbc_connect},
            )
        )


settings = Settings()
settings.backend_cors_origins = settings.backend_cors_origins_list
