# Publicar "Bichos en pantalla" en la Microsoft Store

Por qué: un paquete MSIX publicado en la Store lo **firma Microsoft gratis** al aprobarlo, y la gente lo instala sin avisos de SmartScreen. El registro de desarrollador individual es gratis y sin tarjeta (documento + selfie). Fuentes: [opciones de firma](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options) · [requisitos del paquete](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements) · [registro gratis](https://blogs.windows.com/windowsdeveloper/2025/09/10/free-developer-registration-for-individual-developers-on-microsoft-store/).

## Qué ya está hecho
- `herramientas\crear_msix.bat` arma `dist\tienda\BichosPantalla_<versión>_x64.msix` (+ logos y capturas en `dist\tienda\ficha\`).
- El .exe de tienda **no lleva las arañas con foto** (salen de fotos de banco de imágenes sin licencia de redistribución): solo cucaracha CC0 + arañas dibujadas. Para incluirlas, solo con licencia: `crear_msix.bat --con-aranas`.
- Probado en una PC con modo desarrollador: el manifiesto y los recursos se registran bien y la variante de tienda corre sin errores y sin red. Hasta aprobarlo la Store, un `.msix` sin firmar solo se instala con el modo desarrollador.

## Qué falta (lo hacés vos: identidad y envío)
1. **Registrarte**: <https://storedeveloper.microsoft.com> → cuenta *individual* (gratis; documento + selfie). Ahí se ve si tu país está disponible.
2. **Reservar el nombre** en Partner Center → *Apps y juegos* → *Nueva aplicación* ("Bichos en pantalla"; si está tomado, "Bichos en la pantalla", "Bichos de escritorio"...).
3. **Copiar la identidad** (Partner Center → tu app → *Gestión del producto* → *Identidad de la aplicación*) a `herramientas\msix\identidad.txt`: `NOMBRE` (Package/Identity/Name), `PUBLISHER` (Package/Identity/Publisher) y `EDITOR` (PublisherDisplayName). Exactos: distingue mayúsculas, espacios y signos.
4. Correr `herramientas\crear_msix.bat`. (Mientras `NOMBRE` termine en `.Prueba` el paquete es de prueba y no se puede subir.)
5. En Partner Center → *Iniciar un envío*:
   - **Precio y disponibilidad**: gratis; elegir mercados.
   - **Propiedades**: categoría *Personalización* o *Entretenimiento*; no usa red ni cuentas.
   - **Clasificación por edad**: cuestionario IARC; responder con honestidad (hay preguntas sobre contenido que asusta: insectos realistas).
   - **Paquetes**: subir el `.msix`.
   - **Capacidades restringidas**: pegar la justificación de abajo (`runFullTrust`).
   - **Ficha de la Store (es)**: textos de abajo + `dist\tienda\ficha\` (logo 300×300, logo 1080×1080 y capturas 1920×1080).
   - **Notas para certificación**: texto de abajo.
6. Enviar. La revisión demora de horas a unos días. Para actualizar: subir `VERSION=1.0.1.0` (el último número queda en 0, lo reserva la Store).

## Textos para la ficha (español)
**Nombre:** Bichos en pantalla

**Descripción corta:** Una cucaracha o una araña realista cruza tu escritorio de vez en cuando. Una broma inofensiva.

**Descripción:**
De vez en cuando, al azar, un insecto realista cruza el escritorio por todos tus monitores. Se mueve con patas animadas, proyecta sombra, corre, frena y se asusta si acercás el mouse.

- Cucarachas con fotografías reales y arañas dibujadas.
- Funciona con varios monitores y distintas escalas de pantalla.
- Ventanas transparentes que no bloquean nada: se puede hacer clic a través del bicho.
- Icono en la bandeja (junto al reloj) para soltar uno al instante, elegir con qué frecuencia aparecen, el tipo y el tamaño, y salir.
- No usa internet, no pide ninguna cuenta y no guarda datos personales. Solo escribe sus ajustes y un registro técnico en su propia carpeta.

Es una broma pensada para divertirte a vos o a quien te dé permiso. Mejor no usarla en computadoras ajenas sin avisar a su dueño.

**Palabras clave:** broma, insecto, cucaracha, araña, escritorio, mascota de pantalla, divertido

**Novedades (1.0):** Primera versión.

**Política de privacidad (texto, por si Partner Center pide una URL):** "Bichos en pantalla no recopila, transmite ni comparte información personal. No se conecta a internet. Lee la posición del mouse solo para que el insecto se asuste y no la guarda. Guarda en el equipo del usuario únicamente sus ajustes y un registro técnico (carpeta %LOCALAPPDATA%\BichosPantalla), que no se envían a nadie y se pueden borrar eliminando esa carpeta." (Nota: al subir el paquete, Partner Center marcó "usa información personal" por la capacidad runFullTrust y exigió una política: se cargó como texto, en español e inglés.)

## Justificación de `runFullTrust` (en inglés, para el revisor)
"The app is a classic Win32 desktop program (Python + Qt, built with PyInstaller). It creates transparent, click-through, always-on-top top-level windows to animate an insect on the desktop, and a notification-area (tray) icon. These need the full-trust desktop process model; it uses no network, no personal files, no camera/microphone/location, spawns no other processes and does not touch the registry."

## Notas para certificación (en inglés)
"Spanish-language UI. After launch, a cockroach icon appears in the notification area (near the clock; check the hidden icons arrow). The first insect crosses the screen 6–12 seconds after launch. To see one immediately: right-click the tray icon → 'Soltar ahora'. To exit: right-click the tray icon → 'Salir'. The app is click-through and never takes focus. No sign-in, no network access, no personal data. Settings/log are stored under %LOCALAPPDATA%\BichosPantalla."

## Otros
- Capturas: las de `dist\tienda\ficha\` se generan con el propio render del programa sobre un fondo liso (no capturan tu pantalla). Para la Store conviene reemplazarlas por capturas reales: con el programa corriendo, "Soltar ahora" y `Win+Shift+S` (cuidando que no salga nada personal en la pantalla).
- Si más adelante conseguís fotos de arañas con licencia que permita redistribuir, se regeneran los sprites (ver `herramientas\regenerar_sprites.bat`) y se arma con `--con-aranas`.
- Si la Store no te sirve (país no disponible, rechazo): [SignPath Foundation](https://signpath.io/product/open-source) firma gratis proyectos open source (repo público, licencia OSI); un certificado OV cuesta 150–300 US$/año; Azure Artifact Signing (9,99 US$/mes) no admite individuos fuera de EE. UU. y Canadá. Pasando el .exe por pendrive o red local tampoco aparece SmartScreen.
