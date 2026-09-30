# Agente Publicitario para Facebook

Asistente que publica en **grupos de Facebook** la promoción de tu servicio de
**mantenimiento y reparación de computadoras**, siguiendo un calendario, con reglas
anti-baneo y pruebas automáticas antes de cada publicación.

> ⚠️ **Leé esto primero.** Meta **eliminó en abril de 2024 la API oficial para publicar en
> grupos**, así que no hay forma oficial ni gratuita de automatizar publicaciones en grupos.
> Este agente maneja un navegador real con tu sesión. Automatizar Facebook va contra sus
> Condiciones, así que **siempre hay algún riesgo**. Por eso viene en **modo asistido**:
> el agente prepara todo (abre el grupo, escribe el texto, adjunta las fotos) y **vos hacés
> el clic final en "Publicar"**. Así el riesgo es mucho menor y siempre controlás lo que sale.

---

## 1. Herramientas (todas gratuitas)

| Herramienta | Para qué | Costo |
|---|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | Lenguaje en el que está hecho el agente | Gratis |
| [Playwright](https://playwright.dev/python/) + Chromium | Controla el navegador para publicar | Gratis (código abierto) |
| PyYAML, Pillow, tzdata | Leer la configuración, revisar imágenes, zonas horarias | Gratis |
| pytest | Pruebas automáticas del agente | Gratis |
| Programador de tareas de Windows / carpeta Inicio / `cron` | Que el agente arranque solo | Viene con el sistema |
| [Canva](https://www.canva.com/) (plan gratis) | Diseñar las imágenes de tus publicaciones | Gratis |
| [Meta Business Suite](https://business.facebook.com/) | *Recomendado:* programar publicaciones **oficialmente** en una Página de tu negocio | Gratis |

No se usa ningún servicio pago, ninguna API paga y no hace falta servidor: corre en tu PC.

---

## 2. Plan para que Facebook no nos banee

El agente **ya aplica** estas reglas automáticamente (configurables en `config/config.yaml`):

| Regla | Valor por defecto | Por qué |
|---|---|---|
| Máximo de publicaciones por día (sumando todos los grupos) | 3 | Publicar mucho en poco tiempo es la señal #1 de spam |
| Pausa mínima entre publicaciones | 45 minutos | Evita ráfagas |
| Días de descanso por grupo | 7 días | Los admins y Facebook castigan repetir en el mismo grupo |
| Horario permitido | 09:00 a 21:00 | Una persona no publica a las 4 AM |
| Demora al azar antes de publicar | 30 s a 5 min | Que no sea siempre a la hora exacta |
| Escritura "humana" | letra por letra, con pausas y scroll | No parecer un robot |
| Variaciones de texto `{opción1\|opción2}` | cada grupo recibe un texto distinto | Facebook detecta textos idénticos |
| Bloqueo de textos repetidos | >85 % parecido en el mismo grupo → no se publica | Idem |
| Máximo 1 enlace y 5 hashtags | | Los enlaces son lo que más dispara el filtro de spam |
| Sin ráfagas tras apagar la PC | lo atrasado más de 12 h se descarta | No publicar 10 cosas juntas al prender |
| **Freno de emergencia** | si Facebook muestra "bloqueado temporalmente", "restringida", "confirmá tu identidad", etc. → el agente **se pausa solo** | No insistir cuando Facebook ya avisó |
| Nunca guarda tu contraseña | iniciás sesión vos, a mano, una vez | Seguridad |

Lo que tenés que hacer **vos**:

1. **Calentá la cuenta.** Usá una cuenta real y antigua (no una recién creada). Las primeras
   2 semanas: 1 publicación por día como máximo, en modo `asistido`.
2. **Solo grupos donde seas miembro y que permitan publicidad.** Leé las reglas de cada grupo.
   Si solo aceptan publicidad ciertos días, ponelo en `dias_permitidos`.
3. **Participá, no solo publiques.** Comentá y ayudá en los grupos (por ejemplo, respondiendo
   dudas de computación). Una cuenta que solo publica anuncios es sospechosa.
4. **Respondé rápido** los comentarios y mensajes de tus publicaciones.
5. **Aportá valor**: alterná promociones con consejos ("5 señales de que tu notebook necesita
   limpieza"). Funciona mejor y es menos "spam".
6. **Usá variaciones** `{...|...}` en todos los textos y cambiá las imágenes seguido.
7. **No subas los límites de golpe.** Si en un mes no hubo avisos, podés pasar a 4-5 por día.
8. **Modo `automatico` solo después de semanas sin problemas**, y nunca con `--oculto` al principio.
9. **Si el agente se pausa**: entrá a Facebook a mano, resolvé lo que pida, esperá **al menos
   48-72 h** y recién después ejecutá `python -m agente reanudar`.
10. **Complemento oficial y sin riesgo**: creá una **Página** de tu negocio y programá ahí
    publicaciones con Meta Business Suite (gratis y permitido). Después podés compartirlas en
    los grupos con el agente.

---

## 3. Instalación

### Windows
1. Instalá [Python](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"**.
2. Descargá este proyecto (botón verde *Code → Download ZIP*) y descomprimilo.
3. Doble clic en **`instalar.bat`**.
4. Doble clic en **`iniciar_sesion.bat`**: se abre un navegador, entrás a Facebook normalmente
   y después presionás Enter en la ventana negra.

### Linux / Mac
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -m agente iniciar-sesion
```

> La sesión queda guardada en la carpeta `datos/` (ignorada por git). **Nunca compartas ni
> subas esa carpeta**: tiene tu sesión de Facebook.

---

## 4. Dónde poner las imágenes y los textos

```
publicaciones/
├── imagenes/            ← PONÉ ACÁ TUS FOTOS (.jpg o .png, ideal 1080x1080)
└── programadas.yaml     ← calendario: qué se publica, cuándo y en qué grupos
config/
└── config.yaml          ← tus grupos, límites anti-baneo y modo de trabajo
```

1. Copiá tus fotos a `publicaciones/imagenes/`.
2. En `config/config.yaml` cargá tus grupos (nombre + url del grupo).
3. En `publicaciones/programadas.yaml` agregá tus publicaciones. Ejemplo:

```yaml
publicaciones:
  - id: limpieza-octubre
    fecha: 2026-10-10
    hora: "10:30"
    grupos: [Vecinos Zona Norte, Clasificados de la Ciudad]   # o [todos]
    imagenes: [limpieza-antes-despues.jpg]
    repetir_cada_dias: 14        # opcional
    texto: |
      {¡Hola vecinos!|¡Buenas a todos!} Soy técnico en computadoras.
      {¿Tu PC anda lenta?|¿Tu notebook se calienta?} Hago limpieza, formateo y mejoras.
      {Presupuesto sin cargo.|Consultá sin compromiso.} 📩 Escribime por privado.
```

Si una publicación va a 3 grupos, **no salen juntas**: el agente las reparte respetando la
pausa mínima y el máximo diario.

---

## 5. Programar las publicaciones

- **Dejar el agente trabajando:** doble clic en `ejecutar_agente.bat`
  (o `python -m agente ejecutar`). Revisa el calendario cada ~5 minutos y publica lo que
  corresponda. Podés editar los archivos mientras corre: toma los cambios solo.
- **Que arranque al prender la PC (Windows):** `Win + R` → escribí `shell:startup` → poné ahí
  un acceso directo a `ejecutar_agente.bat`.
- **Linux con cron** (solo modo `automatico`, porque el asistido necesita que estés):
  `*/15 9-21 * * * cd /ruta/al/agente && .venv/bin/python -m agente publicar-pendientes`

En modo `asistido`, cuando llega la hora el agente suena, abre el grupo con el borrador
listo, y te pregunta en la ventana negra si lo publicaste.

---

## 5b. Conexión con GitHub (Claude te prepara publicaciones cada semana)

Si conectás la carpeta con GitHub, el agente **sube** lo que dejás en la PC y **baja** lo que
prepara Claude, solo, cada 30 minutos mientras está andando:

| Vos dejás en la PC | Claude deja en GitHub |
|---|---|
| Fotos nuevas en `publicaciones/imagenes/` | Publicaciones de la semana en `programadas.yaml` |
| Ideas y pedidos en `publicaciones/ideas.txt` | Imágenes nuevas con tus datos |
| | Mejoras del agente |

Cómo conectarla (una sola vez):
1. Instalá [Git para Windows](https://git-scm.com/download/win) (todo "Siguiente").
2. Poné `conectar_github.bat` en la carpeta del agente y abrilo. La primera vez se abre una
   ventana para iniciar sesión en GitHub: aceptá.
3. Listo. Para sincronizar a mano en cualquier momento: `sincronizar.bat`.

La carpeta `datos/` (tu sesión de Facebook) **nunca** se sube.
Las imágenes se generan con `python -m herramientas.imagenes` (ver `herramientas/imagenes.py`).

---

## 6. Pruebas antes de publicar

Hay **tres niveles** de prueba. Hacelos en este orden cada vez que cambies algo:

| Paso | Comando | Qué prueba | ¿Abre Facebook? |
|---|---|---|---|
| 1 | `python -m agente validar` (o `probar.bat`) | Que existan las imágenes, que no estén dañadas, tamaño y peso, largo del texto, enlaces, hashtags, palabras prohibidas, llaves `{}` bien cerradas, grupos existentes, fechas y horarios | No |
| 2 | `python -m agente vista-previa` | Muestra el texto exacto que saldría en cada grupo | No |
| 3 | `python -m agente simular --id limpieza-octubre` | Abre el grupo real, escribe el texto, adjunta las fotos, **saca una captura en `datos/capturas/` y descarta el borrador sin publicar** | Sí, sin publicar |

Además:
- **Antes de cada publicación real** el agente vuelve a correr todas las validaciones y las
  reglas anti-baneo; si algo falla, **no publica** y lo anota en `datos/agente.log`.
- `modo: simulacion` en `config.yaml` corre el calendario completo sin publicar nada.
- `python -m agente estado` muestra cuántas publicaciones van hoy, qué está pendiente (y por
  qué espera), lo próximo programado y los últimos movimientos.
- `python -m agente verificar-sesion` comprueba que sigas logueado y sin advertencias.
- Pruebas del propio agente (para desarrolladores): `pip install -r requirements-dev.txt` y
  `python -m pytest`. Incluyen pruebas con un navegador real contra una página local que
  imita un grupo de Facebook (se ejecutan también en GitHub Actions).

---

## Comandos

| Comando | Descripción |
|---|---|
| `iniciar-sesion` | Abre el navegador para iniciar sesión (una sola vez) |
| `verificar-sesion` | Comprueba la sesión y si hay advertencias de Facebook |
| `validar` | Prueba todas las publicaciones sin abrir Facebook |
| `vista-previa [--id X]` | Muestra el texto final por grupo |
| `simular --id X [--grupo Y]` | Prueba real en Facebook sin publicar |
| `estado` | Resumen de límites, pendientes y movimientos |
| `publicar-pendientes` | Una pasada (publica como máximo 1) — para cron |
| `ejecutar` | Deja el agente trabajando según el calendario |
| `sincronizar` | Sube tus fotos/ideas y baja lo nuevo desde GitHub |
| `reanudar` | Quita la pausa de emergencia |

Todos se usan como `python -m agente <comando>` (con el entorno `.venv` activado).

## Si algo no funciona

- **"No se encontró el cuadro 'Escribe algo...'"**: Facebook cambia su página seguido.
  Corré `simular` y mirá la captura en `datos/capturas/`. Verificá que seas miembro del grupo.
  Si Facebook cambió los textos de los botones, se ajustan en `agente/publicador.py`
  (`TEXTO_COMPOSITOR`, `BOTON_FOTO`, `BOTON_PUBLICAR`).
- **"Ya hay otro agente trabajando"**: cerrá la otra ventana, o borrá `datos/agente.lock`.
- **El agente quedó pausado**: leé el motivo con `estado`, revisá tu cuenta y usá `reanudar`.
- Todo queda registrado en `datos/agente.log` y `datos/historial.json`.
