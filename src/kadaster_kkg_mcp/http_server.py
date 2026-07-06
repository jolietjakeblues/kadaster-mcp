import os

from kadaster_kkg_mcp.server import mcp


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.environ["PORT"])

    mcp.settings.host = host
    mcp.settings.port = port
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()