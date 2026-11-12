"""Prepara una fotografía antes de enviarla a un proveedor de IA.

La imagen se reduce (menos datos fuera del servidor y menor costo) y se vuelve
a codificar como JPEG sin metadatos: así no viajan la fecha, el modelo del
teléfono ni las coordenadas GPS que las cámaras guardan dentro del archivo. El
original guardado en el servidor no se modifica.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

PHOTO_EXTENSIONS = frozenset({"jpg", "jpeg", "png"})
MAX_SIDE = 1600
MAX_PIXELS = 60_000_000
JPEG_QUALITY = 85


class PhotoError(Exception):
    """La imagen no se pudo leer."""


def prepare_photo(content: bytes) -> bytes:
    """JPEG reducido, con la orientación corregida y sin metadatos."""
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise PhotoError("imagen demasiado grande")
            # La orientación se aplica a los píxeles porque el metadato se descarta.
            upright = ImageOps.exif_transpose(image)
            if upright.mode not in ("RGB", "L"):
                # Las transparencias se aplanan sobre blanco.
                rgba = upright.convert("RGBA")
                flat = Image.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.getchannel("A"))
                upright = flat
            upright.thumbnail((MAX_SIDE, MAX_SIDE))
            output = io.BytesIO()
            # Guardar sin ``exif`` ni ``icc_profile`` deja fuera todos los metadatos.
            upright.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY)
            return output.getvalue()
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise PhotoError("imagen ilegible") from error
