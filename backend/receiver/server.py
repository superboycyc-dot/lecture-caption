import asyncio
from hypercorn.asyncio import serve
from hypercorn.config import Config
from app import create_app

config = Config()
config.bind = ["127.0.0.1:18765"]
config.workers = 1
config.accesslog = None
config.errorlog = None
config.read_timeout = 10
config.keep_alive_timeout = 3
config.graceful_timeout = 20
config.h11_max_incomplete_size = 16384
config.h2_max_concurrent_streams = 16
config.backlog = 64
config.include_server_header = False
config.include_date_header = False
asyncio.run(serve(create_app(), config))
