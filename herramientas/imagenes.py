"""Generador de placas publicitarias 1080x1080 con los datos del negocio.

Uso:
    python -m herramientas.imagenes   (regenera la placa principal)

Desde código:
    from herramientas.imagenes import placa, placa_con_foto
    placa("SERVICIO TÉCNICO", "Netbooks · Notebooks · PC", ["Ítem 1", "Ítem 2"], "salida.png", tema="azul")
    placa_con_foto("publicaciones/fondos/taller.jpg", "TÍTULO", "Subtítulo", ["Ítem 1"], "salida.png")

Las fotos de fondo (generadas con IA sin texto, o fotos propias) van en publicaciones/fondos/.
El texto siempre lo escribe este programa, así los datos (dirección, WhatsApp) nunca salen mal.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_IMAGENES = RAIZ / "publicaciones" / "imagenes"

NEGOCIO = {
    "direccion": "Monteagudo 1140",
    "ciudad": "Tafí Viejo",
    "whatsapp": "381 649-6790",
    "pie": "Recibimos tarjetas de crédito",
}

TEMAS = {
    #        fondo arriba    fondo abajo     acento          texto           suave
    "azul":  ((12, 34, 64), (22, 64, 124), (255, 196, 0), (255, 255, 255), (170, 210, 255)),
    "verde": ((10, 48, 40), (18, 96, 72), (255, 214, 64), (255, 255, 255), (170, 235, 205)),
    "rojo":  ((70, 14, 20), (140, 28, 40), (255, 214, 64), (255, 255, 255), (255, 200, 200)),
    "negro": ((18, 18, 22), (48, 48, 58), (0, 200, 255), (255, 255, 255), (190, 190, 205)),
}

_FUENTES = {
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"],
}
W = H = 1080


def _fuente(tam: int, negrita: bool = True):
    for ruta in _FUENTES[negrita]:
        if Path(ruta).is_file():
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default(size=tam)


def _ajustar(d: ImageDraw.ImageDraw, texto: str, tam: int, ancho_max: int, negrita: bool = True):
    """Achica la letra hasta que el texto entre en el ancho disponible."""
    while tam > 20 and d.textlength(texto, font=_fuente(tam, negrita)) > ancho_max:
        tam -= 2
    return _fuente(tam, negrita)


def placa(titulo: str, subtitulo: str, items: list[str], salida: str | Path, tema: str = "azul") -> Path:
    arriba, abajo, acento, texto, suave = TEMAS[tema]
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(arriba, abajo)))

    def centrado(y, contenido, fuente, color):
        d.text(((W - d.textlength(contenido, font=fuente)) / 2, y), contenido, font=fuente, fill=color)

    d.rectangle([0, 0, W, 190], fill=acento)
    centrado(35, titulo, _ajustar(d, titulo, 64, W - 80), arriba)
    centrado(115, subtitulo, _ajustar(d, subtitulo, 44, W - 80), arriba)

    items = items[:5]
    paso = 430 // max(len(items), 1)
    y = 235
    for item in items:
        d.ellipse([100, y + 10, 132, y + 42], fill=acento)
        d.line([(108, y + 26), (115, y + 34), (126, y + 17)], fill=arriba, width=5)
        d.text((160, y), item, font=_ajustar(d, item, 42, W - 200, negrita=False), fill=texto)
        y += min(paso, 90)

    d.rounded_rectangle([80, 690, 1000, 900], radius=28, outline=acento, width=5)
    centrado(710, NEGOCIO["direccion"], _fuente(54), texto)
    centrado(780, NEGOCIO["ciudad"], _fuente(42), suave)
    centrado(840, f"WhatsApp {NEGOCIO['whatsapp']}", _fuente(42), acento)
    centrado(950, NEGOCIO["pie"], _fuente(44), acento)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    im.save(salida, optimize=True)
    return salida


def placa_con_foto(fondo: str | Path, titulo: str, subtitulo: str, items: list[str], salida: str | Path,
                   tema: str = "azul", subir_foto: float = 0.25) -> Path:
    """Foto arriba y los datos del negocio sobre un degradado oscuro abajo.

    subir_foto: cuánto se sube la foto (0 a 0.4) para que se vea el centro/abajo de la imagen,
    donde suele estar lo importante (la notebook, las manos, etc.).
    """
    arriba, _, acento, texto, suave = TEMAS[tema]
    with Image.open(fondo) as foto:
        foto = foto.convert("RGB")
        lado = min(foto.size)
        izq, sup = (foto.width - lado) // 2, (foto.height - lado) // 2
        foto = foto.crop((izq, sup, izq + lado, sup + lado)).resize((W, H), Image.LANCZOS)
    im = Image.new("RGB", (W, H), arriba)
    im.paste(foto, (0, 170 - int(H * max(0.0, min(subir_foto, 0.4)))))

    # Degradado oscuro desde la mitad hacia abajo para que el texto se lea sobre cualquier foto.
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    inicio = 380
    for y in range(inicio, H):
        t = min(1.0, (y - inicio) / 200)
        opacidad = int(235 * t) if y < 700 else min(255, 235 + (y - 700) // 4)  # opaco al final
        dc.line([(0, y), (W, y)], fill=(*arriba, opacidad))
    im = Image.alpha_composite(im.convert("RGBA"), capa).convert("RGB")
    d = ImageDraw.Draw(im)

    def centrado(y, contenido, fuente, color):
        d.text(((W - d.textlength(contenido, font=fuente)) / 2, y), contenido, font=fuente, fill=color)

    d.rectangle([0, 0, W, 170], fill=acento)
    centrado(28, titulo, _ajustar(d, titulo, 62, W - 80), arriba)
    centrado(105, subtitulo, _ajustar(d, subtitulo, 42, W - 80), arriba)

    y = 560
    for item in items[:4]:
        d.ellipse([100, y + 8, 128, y + 36], fill=acento)
        d.line([(107, y + 22), (113, y + 29), (122, y + 15)], fill=arriba, width=4)
        d.text((150, y), item, font=_ajustar(d, item, 38, W - 190, negrita=False), fill=texto)
        y += 58

    d.rounded_rectangle([80, 810, 1000, 985], radius=26, outline=acento, width=4)
    centrado(825, f"{NEGOCIO['direccion']} · {NEGOCIO['ciudad']}",
             _ajustar(d, f"{NEGOCIO['direccion']} · {NEGOCIO['ciudad']}", 46, 880), texto)
    centrado(885, f"WhatsApp {NEGOCIO['whatsapp']}", _fuente(46), acento)
    centrado(942, NEGOCIO["pie"], _fuente(32, negrita=False), suave)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    im.save(salida, quality=90, optimize=True)
    return salida


if __name__ == "__main__":
    ruta = placa(
        "SERVICIO TÉCNICO", "Netbooks · Notebooks · PC",
        ["Reparación y mantenimiento", "Desbloqueo de netbooks G1 a G15", "Windows 7, 8, 10 y 11",
         "Office, Acrobat, Photoshop, Corel", "Asistencia remota a distancia"],
        CARPETA_IMAGENES / "servicio-tecnico-tafi.png",
    )
    print(f"Imagen guardada en {ruta}")
