@echo off
rem Regenera sprites\ (cuerpos y patas con fotos reales) a partir de las fotos de fotos\.
rem Las coordenadas (elipses del cuerpo y tramos de pata) están en píxeles de cada foto original.
cd /d "%~dp0"

python preparar_foto.py "..\fotos\originales\cucaracha_B.jpg" --tipo cucaracha ^
  --pata "2950,1896,3476,1992,260"

python preparar_foto.py "..\fotos\trochosa-ruricola-wolf-spider-1000x1000-rentokil-species-adobestock-1584017857.webp" ^
  --tipo arana --nombre arana_lobo ^
  --elipses "470,482,62,58;607,480,86,55" ^
  --femur "548,425,600,343,90" --pata "600,343,930,182,110"

python preparar_foto.py "..\fotos\mexican-red-knee-tarantula-spider-crawling-isolated-animal-specimen-shown-from-top-view-bright-orange-and-black-colors-on-a-transparent-background-png.webp" ^
  --tipo arana --nombre arana_tarantula ^
  --elipses "172,178,37,36;256,168,46,30,-6" ^
  --femur "148,139,100,134,34" --pata "100,134,8,124,40"

pause
