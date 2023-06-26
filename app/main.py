from fastapi import FastAPI, Request
import uvicorn
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from board import Board

templates = Jinja2Templates(directory="app/templates/")

app = FastAPI()
board = Board()
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "board": board.friendly_form.tolist()}
    )


if __name__ == "__main__":
    uvicorn.run(app)
