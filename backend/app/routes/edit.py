"""Face swap + virtual try-on (dress change) endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Form

from ..jobs import manager
from ..providers import faceswap, tryon
from .media import _resolve

router = APIRouter()


@router.post("/faceswap")
async def face_swap(
    target: str = Form(...),       # photo whose face gets replaced
    source_face: str = Form(...),  # photo of the face to insert
) -> dict:
    tgt = _resolve(target)
    src = _resolve(source_face)
    job = manager.submit("edit.faceswap",
                         lambda pr: faceswap.swap(src, tgt, pr))
    return {"job_id": job.id}


@router.post("/tryon")
async def virtual_tryon(
    person: str = Form(...),        # photo of the person
    garment: str = Form(...),       # photo of the clothing item
    category: str = Form("upper_body"),  # upper_body | lower_body | dresses
    description: str = Form(""),
) -> dict:
    per = _resolve(person)
    gar = _resolve(garment)
    params = {"category": category, "description": description}
    job = manager.submit("edit.tryon",
                         lambda pr: tryon.change_outfit(per, gar, params, pr))
    return {"job_id": job.id}
