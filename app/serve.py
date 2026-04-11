import os

import uvicorn


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    workers = int(os.getenv("WEB_CONCURRENCY", "2"))
    keep_alive = int(os.getenv("UVICORN_KEEP_ALIVE", "30"))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=workers,
        proxy_headers=True,
        timeout_keep_alive=keep_alive,
    )


if __name__ == "__main__":
    main()
