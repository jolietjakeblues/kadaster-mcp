import os

from mcp.server.transport_security import TransportSecuritySettings
from kadaster_kkg_mcp.server import mcp


def main() -> None:
    mcp.settings.host = os.getenv("HOST", "0.0.0.0")
    mcp.settings.port = int(os.environ["PORT"])
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "kadaster-mcp.onrender.com",
            "kadaster-mcp.onrender.com:*",
            "localhost",
            "127.0.0.1",
        ],
        allowed_origins=[
            "https://claude.ai",
            "https://kadaster-mcp.onrender.com",
        ],
    )

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()