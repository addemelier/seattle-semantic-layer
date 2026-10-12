"""Run the permit map: python -m permitmap.app"""

import uvicorn

from permitmap.app.config import Config
from permitmap.app.main import create_app


def main() -> None:
    config = Config.from_env()
    uvicorn.run(create_app(config), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
