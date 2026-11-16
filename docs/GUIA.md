# Bichos en pantalla — guía técnica

> Resumen para usuarios y descarga: ver el [README](../README.md). Esta guía detalla uso, seguridad, registros y cómo agregar fotos.

De vez en cuando (al azar) una cucaracha o una araña cruza el escritorio, por todos tus monitores.

## Usar
- `iniciar.bat` – arranca en segundo plano (icono en la bandeja, junto al reloj).
- `soltar_ya.bat` – arranca y suelta uno enseguida.
- Botón derecho en el icono: soltar ahora, frecuencia, tipo de insecto, tamaño, "se asusta del mouse", **Ver registro (log)** y Salir. (La versión de desarrollo agrega "Iniciar con Windows"; el .exe no la tiene a propósito.)
- Ajustes guardados en `bichos.ini`.

## El .exe (para otras computadoras)
- `dist\BichosPantalla.exe` (~21 MB): un solo archivo, trae Python, Qt y las fotos adentro. Windows 10/11 de 64 bits, **no hay que instalar nada**. Tarda 2–4 s en arrancar (se descomprime solo).
- Para usarlo: copiarlo a la otra PC (pendrive, mail, nube) y hacer doble clic. Aparece el icono de la cucaracha en la bandeja, junto al reloj; el primer bicho sale a los 6–12 s. Configuración por defecto: tamaño mediano, uno cada 1–4 min.
- Cerrarlo: botón derecho en el icono → **Salir**.
- No escribe junto al .exe: sus ajustes y logs quedan en `%LOCALAPPDATA%\BichosPantalla` (`bichos.ini`, `bichos.log`).
- Windows puede mostrar el aviso de **SmartScreen** ("Windows protegió su PC") porque el .exe no está firmado: *Más información → Ejecutar de todas formas*. Si lo pasás por pendrive suele no aparecer.
- Desinstalar: Salir, borrar el .exe y la carpeta `%LOCALAPPDATA%\BichosPantalla`. No deja nada más (no toca el registro ni se instala).
- Usalo en computadoras ajenas solo con permiso de su dueño.
- Rehacerlo: `herramientas\crear_exe.bat` (usa `herramientas\BichosPantalla.spec`). Si cambian las fotos, primero `herramientas\regenerar_sprites.bat`; el icono sale de `herramientas\hacer_icono.py`.

## Microsoft Store (paquete MSIX, firma gratis de Microsoft)
- `herramientas\crear_msix.bat` arma `dist\tienda\BichosPantalla_1.0.0.0_x64.msix` con un .exe **sin las arañas de foto** (solo cucaracha CC0 + arañas dibujadas), más logos y capturas para la ficha en `dist\tienda\ficha\`.
- Falta la identidad real: registrarse (gratis) en <https://storedeveloper.microsoft.com>, reservar el nombre y copiar los datos a `herramientas\msix\identidad.txt`. Guía paso a paso y textos listos para pegar: `herramientas\msix\LEEME_STORE.md`.
- Con la identidad de prueba que trae `identidad.txt` el paquete solo sirve para probar en tu PC (modo desarrollador); no se puede subir.

## Seguridad (revisión del 2026-11-15)
**Qué hace el programa y nada más:** dibuja ventanas transparentes con un bicho y las mueve; lee la posición del mouse (solo para que el bicho se asuste; no se guarda ni se registra); guarda sus ajustes y un log técnico en su propia carpeta.

**Qué NO hace (comprobado):**
- Red: 0 conexiones TCP/UDP medidas con el programa corriendo; dentro del .exe no hay OpenSSL, `socket`, `ssl`, `http`, `urllib`, `smtplib`, `ftplib` ni Qt Network. (`ws2_32.dll`/`netapi32.dll` aparecen cargadas porque `Qt6Core.dll` y Python las enlazan por defecto; no se usan.)
- No lanza otros programas por su cuenta (sin `subprocess`; ningún proceso hijo observado) y no usa `eval`/`pickle`. Única excepción, a pedido del usuario: el menú *Ver registro (log)* abre `bichos.log` con el editor de texto predeterminado (`os.startfile`).
- No captura pantalla, teclado ni portapapeles. Las funciones de prueba que sacan capturas están en `devtools.py`, que **no entra al .exe**, y el .exe ignora `--test`, `--png`, `--probar-pantallas` y `--debug`.
- No toca el registro de Windows (el módulo `winreg` está excluido) y no se auto-instala ni se inicia solo.
- No pide administrador: manifiesto `asInvoker` (permisos de usuario normal, sin UAC).
- Ignora las variables `QT_*` del entorno (probado con `QT_QPA_PLATFORM=minimal` y `QT_PLUGIN_PATH` falso): solo carga los plugins que trae.

**Qué muestra y qué guarda:** en pantalla, solo el bicho, el icono y su menú. El log guarda versión de Python/Qt/Windows, geometría de los monitores identificados como P0/P1 (sin nombre de modelo), cada bicho (tipo, posición) y errores; las rutas personales (`C:\Users\nombre`) se enmascaran como `~`. Nunca sale de la PC. El .exe no contiene nombres, correos ni rutas del equipo donde se compiló, y las imágenes no traen EXIF/GPS.

**Dependencias (pip-audit):** PyQt6 6.12.1, Qt 6.12.0, PyInstaller 6.22.3 y compañía, sin vulnerabilidades conocidas. Pillow (solo herramienta de preparación, no va en el .exe) se actualizó a 13.0.0 por 42 vulnerabilidades, y `certifi`/`urllib3` (solo del entorno de desarrollo, tampoco van en el .exe) a 2026.10.23 / 2.8.0. Windows Defender: sin hallazgos.

**Límites que quedan:**
- El .exe no está firmado digitalmente (hace falta un certificado de pago): SmartScreen y algunos antivirus pueden desconfiar.
- Lleva el runtime de Python con el que se compiló (hoy **3.14.10**, versión de seguridad del 25/10/2026, compilado el 15/11/2026). Si sale una 3.14.x más nueva con arreglos de seguridad, conviene actualizar Python y rehacer el .exe.
- Es un .exe de un solo archivo: al abrirse se descomprime en `%TEMP%\_MEIxxxxx` (carpeta del propio usuario). Es el comportamiento normal de PyInstaller; otro programa del mismo usuario podría tocar esa carpeta, pero eso no le da más permisos de los que ya tiene.

## Si algo falla: registros
- (Con el .exe, estos archivos están en `%LOCALAPPDATA%\BichosPantalla`; con "Ver registro (log)" del icono se abre el correcto.)
- `bichos.log` – todo lo que pasa: monitores, cada bicho (cuándo aparece, por qué monitor pasa, cuándo se va), errores de Python y mensajes de Qt. Rota solo (máx. ~2 MB).
- `bichos_fallo.log` – volcado de pila si el proceso muere por un error nativo.
- Si la corrida anterior terminó mal (crash), la siguiente lo avisa en `bichos.log` con la línea "La corrida anterior NO terminó bien". Si no hay "Cierre normal" al final de una corrida, fue un crash.
- Solo en desarrollo (`python bichos.py ...`): `--probar-pantallas` cruza todos los monitores y deja el resultado en el log; `--debug` agrega mensajes detallados de Qt; `--test` y `--png` hacen capturas/hojas de prueba. Viven en `devtools.py`.

## Cómo se ve
- Cuerpos y patas salen de **fotos reales** (carpeta `sprites\`, generada con `herramientas\preparar_foto.py`). Las patas se animan con cinemática inversa.
- Si falta un sprite, se dibuja el cuerpo vectorial de antes.
- `herramientas\regenerar_sprites.bat` rehace los sprites desde `fotos\` (ahí están las coordenadas usadas).

## Agregar otra foto
Condiciones: vista **desde arriba**, bicho **entero** (con las patas), fondo liso claro o PNG/WebP transparente, bien enfocado, al menos ~1000 px, patas abiertas como caminando, cabeza hacia cualquier lado. Para arañas hay que indicar a mano 2 elipses (cefalotórax y abdomen) y 1–2 tramos de pata; ver ejemplos en `regenerar_sprites.bat` y la ayuda de `preparar_foto.py` (`--debug` dibuja lo elegido sobre la foto).

## Derechos de las fotos y git
- `fotos\originales\`: fotos de Alex Wild / Insects Unlocked (Univ. de Texas), **CC0** (dominio público), bajadas de Wikimedia Commons. Solo se usó `cucaracha_B.jpg`.
- Las fotos de arañas que el autor usa en su copia personal parecen de bancos de imágenes: **no se incluyen en este repositorio ni en los .exe publicados** (las arañas se dibujan vectoriales). Para tener arañas con foto usá fotos propias o con licencia que permita redistribuir.
- Por eso `.gitignore` deja afuera `fotos\` y los sprites de arañas (derivados de esas fotos), además de `dist\`, logs y ajustes. Sin esos sprites el programa dibuja las arañas con el cuerpo vectorial.
