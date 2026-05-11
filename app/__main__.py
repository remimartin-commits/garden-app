from .cli import cli
from fastapi import FastAPI

app = FastAPI()

if __name__ == "__main__":
    cli()
