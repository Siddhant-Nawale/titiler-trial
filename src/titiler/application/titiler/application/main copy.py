"""titiler app."""

import logging

import jinja2
from fastapi import Depends, FastAPI, HTTPException, Security, Query
from fastapi.security.api_key import APIKeyQuery
from fastapi.middleware.cors import CORSMiddleware
from rio_tiler.io import STACReader
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from starlette_cramjam.middleware import CompressionMiddleware
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.factory import TilerFactory
from titiler.application.settings import ApiSettings

logging.getLogger("botocore.credentials").disabled = True
logging.getLogger("botocore.utils").disabled = True
logging.getLogger("rio-tiler").setLevel(logging.ERROR)

templates = Jinja2Templates(
    directory="",
    loader=jinja2.ChoiceLoader([jinja2.PackageLoader(__package__, "templates")]),
)

api_settings = ApiSettings()

# Setup a global API access key, if configured
api_key_query = APIKeyQuery(name="access_token", auto_error=False)


def validate_access_token(access_token: str = Security(api_key_query)):
    """Validates API key access token, set as the `api_settings.global_access_token` value.
    Returns True if no access token is required, or if the access token is valid.
    Raises an HTTPException (401) if the access token is required but invalid/missing."""
    if api_settings.global_access_token is None:
        return True

    if not access_token:
        raise HTTPException(status_code=401, detail="Missing `access_token`")

    # if access_token == `token` then OK
    if access_token != api_settings.global_access_token:
        raise HTTPException(status_code=401, detail="Invalid `access_token`")

    return True


app = FastAPI(
    title=api_settings.name,
    openapi_url="/api",
    docs_url="/api.html",
    description="""A modern dynamic tile server built on top of FastAPI and Rasterio/GDAL.

---

**Documentation**: <a href="https://developmentseed.org/titiler/" target="_blank">https://developmentseed.org/titiler/</a>

**Source Code**: <a href="https://github.com/developmentseed/titiler" target="_blank">https://github.com/developmentseed/titiler</a>

---
    """,
    version=api_settings.version,
    root_path=api_settings.root_path,
    dependencies=[Depends(validate_access_token)],
)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple Dataset endpoints (e.g Cloud Optimized GeoTIFF)
if not api_settings.disable_cog:
    cog = TilerFactory(
        router_prefix="/cog",
        extensions=[],
    )

    app.include_router(
        cog.router,
        prefix="/cog",
        tags=["Cloud Optimized GeoTIFF"],
    )


@app.get(
    "/cog/tiles/{z}/{x}/{y}.png",
    description="Tile endpoint",
    tags=["Tile"],
    response_class=HTMLResponse,
)
def tile_endpoint(
    z: int,
    x: int,
    y: int,
    url: str = Query(..., title="Signed URL to the COG file"),
):
    """
    Tile the Cloud Optimized GeoTIFF (COG) specified by the signed URL.

    :param z: Tile zoom level
    :param x: Tile X coordinate
    :param y: Tile Y coordinate
    :param url: Signed URL to the COG file
    :return: Tiled image
    """
    # Pass the signed URL to Titiler
    request = {
        "url": url,
        "tile_format": "png",
        "tile_matrix": z,
        "tile_x": x,
        "tile_y": y,
        "width": 256,
        "height": 256,
    }

    response = cog.router.tiler(**request)
    if response.status_code == 200:
        return response
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)
