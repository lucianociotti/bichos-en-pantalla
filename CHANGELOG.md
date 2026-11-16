# Cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versiones: `MAYOR.MENOR.PARCHE`.

## [Sin publicar]
Ideas anotadas para próximas versiones:
- **Sonidos**: pasitos sutiles, chillido o "crunch" al aplastarlo. Para no engordar el .exe ni sumar dependencias, usar `winsound` (biblioteca estándar de Windows, WAV) en vez de Qt Multimedia, que agrega ffmpeg y decenas de MB.
- **Interacciones**: aplastarlo con clic o atajo de teclado, que se esconda debajo de las ventanas, que corra por el borde de la pantalla, reaccionar a ventanas abiertas, más especies.
- Arañas con foto, con fotos propias o de licencia que permita redistribuir.
- Firma digital del .exe (certificado o SignPath) y publicación en la Microsoft Store.

## [1.0.0] - 2026-11-16
Primera versión pública.
- Una cucaracha o una araña cruza todos los monitores al azar; patas animadas con cinemática inversa, sombra, carreras y frenadas.
- Cucaracha con **fotos reales** (CC0); arañas dibujadas (vectoriales).
- Se asusta si acercás el mouse (opcional).
- Icono en la bandeja: soltar ahora, frecuencia, insecto, tamaño, ver registro, salir.
- Soporta varios monitores con distinta escala de pantalla.
- Un solo .exe de ~21 MB sin instalación. Sin red, sin captura de pantalla, sin administrador.
