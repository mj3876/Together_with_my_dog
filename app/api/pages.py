from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from app.core.config import ROOT
from app.repositories.place_repository import get_place

router = APIRouter()
templates = Jinja2Templates(directory=str(ROOT / "app/templates"))


def render(request, template, **context):
    return templates.TemplateResponse(request=request, name=template,
                                      context={"is_demo": request.app.state.settings.mode == "demo", **context})


@router.get("/", include_in_schema=False)
def home(request: Request):
    return render(request, "index.html")


@router.get("/saved", include_in_schema=False)
def saved(request: Request):
    return render(request, "saved.html")


@router.get("/places/{place_id}", include_in_schema=False)
def place_detail(place_id: str, request: Request):
    place = get_place(request.app.state.engine, place_id)
    if place is None:
        raise HTTPException(404, "장소를 찾을 수 없습니다.")
    return render(request, "place_detail.html", place=place)
