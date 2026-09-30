"""Flyer de servicios de celulares con los datos actuales, en el estilo del flyer original.

Fondo: publicaciones/fondos/fondo-plateado-celulares.jpg (generado con IA, sin texto).
Reutiliza del flyer viejo (Serviciotecnico1.jpg) la foto del microscopio, el logo PCELL y el ícono de WhatsApp.

Uso:  python -m herramientas.flyer_celulares
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .imagenes import CARPETA_IMAGENES, NEGOCIO, RAIZ

ORIGINAL = CARPETA_IMAGENES / "Serviciotecnico1.jpg"
FONDO = RAIZ / "publicaciones" / "fondos" / "fondo-plateado-celulares.jpg"
SALIDA = CARPETA_IMAGENES / "servicios-celulares.jpg"

W, H = 1300, 919
SERIF = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf"]
TINTA = (18, 18, 28)
FLECHAS = [(214, 30, 40), (120, 50, 200), (20, 90, 190), (240, 110, 20), (40, 150, 230)]

SERVICIOS = [
    ["Cambio de módulos y vidrios"],
    ["Reparación de pin de carga"],
    ["Desbloqueo banda negativa"],
    ["Software, desbloqueo", "de patrón de seguridad"],
    ["Venta de celulares e insumos"],
]


def _fuente(tam: int):
    for ruta in SERIF:
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            continue
    return ImageFont.load_default(size=tam)


def versalitas(d: ImageDraw.ImageDraw, x: float, y: float, texto: str, tam: int, color=TINTA,
               medir: bool = False) -> float:
    """Escribe en versalitas (como el flyer original): mayúsculas grandes y el resto en mayúsculas chicas.
    y es la línea de base. Devuelve el ancho."""
    grande, chica = _fuente(tam), _fuente(int(tam * 0.78))
    inicio = x
    for c in texto:
        fuente = grande if (c.isupper() or c.isdigit()) else chica
        if not medir:
            d.text((x, y), c.upper(), font=fuente, fill=color, anchor="ls")
        x += d.textlength(c.upper(), font=fuente)
    return x - inicio


def _con_brillo(base: Image.Image, dibujar) -> Image.Image:
    """Dibuja el texto con un halo blanco detrás, como el original."""
    capa = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dibujar(ImageDraw.Draw(capa))
    alfa = capa.split()[3]
    halo = Image.new("RGBA", base.size, (255, 255, 255, 0))
    halo.putalpha(alfa.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8)))
    base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, halo)
    return Image.alpha_composite(base, capa)


def _circulo(img: Image.Image, centro, radio, pluma=0) -> Image.Image:
    cx, cy = centro
    recorte = img.crop((cx - radio, cy - radio, cx + radio, cy + radio)).convert("RGBA")
    mascara = Image.new("L", recorte.size, 0)
    ImageDraw.Draw(mascara).ellipse([pluma, pluma, 2 * radio - pluma, 2 * radio - pluma], fill=255)
    if pluma:
        mascara = mascara.filter(ImageFilter.GaussianBlur(pluma / 2))
    recorte.putalpha(mascara)
    return recorte


def _flecha(d: ImageDraw.ImageDraw, x, y, color, numero):
    """Flecha doble con número, como las del flyer original. (x, y) = centro izquierdo."""
    oscuro = tuple(int(c * 0.6) for c in color)
    for dx, col in ((22, oscuro), (0, color)):
        d.polygon([(x + dx, y - 22), (x + dx + 34, y - 22), (x + dx + 58, y), (x + dx + 34, y + 22),
                   (x + dx, y + 22), (x + dx + 20, y)], fill=col)
    d.ellipse([x - 8, y - 16, x + 24, y + 16], fill=color, outline=(255, 255, 255), width=2)
    d.text((x + 8, y), numero, font=_fuente(15), fill=(255, 255, 255), anchor="mm")


def generar() -> None:
    original = Image.open(ORIGINAL).convert("RGB")
    im = Image.open(FONDO).convert("RGB").resize((W, H), Image.LANCZOS).convert("RGBA")
    im = Image.alpha_composite(im, Image.new("RGBA", (W, H), (255, 255, 255, 40)))  # un poco más claro

    # Foto redonda del microscopio con aro brillante
    foto = _circulo(original, (268, 318), 160, pluma=4)
    aro = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(aro).ellipse([95, 150, 445, 500], fill=(255, 255, 255, 230))
    im = Image.alpha_composite(im, aro.filter(ImageFilter.GaussianBlur(10)))
    im.alpha_composite(foto, (108, 158))

    # Logo PCELL, fundido con el fondo
    logo = original.crop((20, 610, 470, 800)).convert("RGBA")
    mascara = Image.new("L", logo.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle([12, 12, logo.width - 12, logo.height - 12], radius=60, fill=255)
    logo.putalpha(mascara.filter(ImageFilter.GaussianBlur(12)))
    im.alpha_composite(logo, (30, 640))

    def textos(d: ImageDraw.ImageDraw):
        titulo = "Nuestros servicios de celulares..."
        ancho = versalitas(d, 0, 0, titulo, 58, medir=True)
        versalitas(d, (W - ancho) / 2 + 20, 118, titulo, 58)
        y = 215
        for lineas in SERVICIOS:
            for i, linea in enumerate(lineas):
                versalitas(d, 620, y + i * 52, linea, 40)
            y += 52 * len(lineas) + 20
        for i, linea in enumerate(["Y mucho más... ¡Te esperamos!", "Trabajos con garantía", "y entrega rápida"]):
            ancho = versalitas(d, 0, 0, linea, 38, medir=True)
            versalitas(d, 880 - ancho / 2, 650 + i * 52, linea, 38)
        direccion = f"{NEGOCIO['direccion']} - {NEGOCIO['ciudad']}"
        ancho = versalitas(d, 0, 0, direccion, 38, medir=True)
        versalitas(d, 880 - ancho / 2, 820, direccion, 38)
        versalitas(d, 700, 886, f"WhatsApp: {NEGOCIO['whatsapp']}", 38)

    im = _con_brillo(im, textos)
    d = ImageDraw.Draw(im)
    y = 215
    for i, lineas in enumerate(SERVICIOS):
        _flecha(d, 540, y - 14, FLECHAS[i], f"0{i + 1}")
        y += 52 * len(lineas) + 20

    im.alpha_composite(_circulo(original, (545, 855), 30).resize((56, 56), Image.LANCZOS), (632, 845))
    im.convert("RGB").save(SALIDA, quality=92, optimize=True)
    print(f"Imagen guardada en {SALIDA}")


if __name__ == "__main__":
    generar()
