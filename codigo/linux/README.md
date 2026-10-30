# codigo/linux — el trabajo con la Jetson Orin Nano

Lo de esta carpeta es para la meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (`specs/007-jetson/`). Se completa fase por fase; al cerrar la meta, en la fase 9 · Cómo se trabaja con la Jetson y cierre de la meta, dirá cómo llega el código, cómo se corren la suite y el tracker, cómo se paran y cómo se corta el acceso.

Hoy (fase 1 · El escaneo de la Jetson, solo lectura) solo hay el escaneo. Ningún agente se conecta a la Jetson: lo corre el autor con su cuenta y su alias. Hasta que la fase 2 · La barrera de seguridad para los agentes esté cumplida, ningún agente usa `ssh` hacia la Jetson.

## Qué hay

- `escanear_jetson.sh`: el escaneo, en bash. Solo lee y lo imprime todo por la salida estándar; en la Jetson no escribe nada. Doce secciones: sistema, Python, CPU y GPU, memoria, disco, USB, V4L2, red, servicios, energía, temperatura y la cuenta. Cada orden lleva `timeout` de 10 s (10 s de `tegrastats`, cortado a propósito), ninguna empieza pasados 90 s y todo queda bajo 120 s. Al final, un `find` del HOME con `-newermt` dice si cambió algo desde el inicio (tiene que salir vacío).
- `escanear.ps1`: lo lanza desde el PC. Manda el script por la entrada estándar de `ssh <alias> timeout -k 5 120 bash --norc --noprofile -s` con `Start-Process` (una tubería de PowerShell 5.1 cambiaría los fines de línea), guarda lo que llega en un archivo que no pisa y espera con tope.
- Las pruebas, en `codigo/tests/test_escaneo_jetson.py`: el script es ASCII y LF, no trae ninguna orden que cambie algo, ni tuberías ni redirecciones a un archivo, y cada orden pasa por `timeout`. Además lo ejecutan con bash y un `PATH` que solo tiene un `timeout` falso, así que no corre ninguna orden real, y comprueban que `escanear.ps1` para con 2 ante una entrada que no vale, antes de conectar. Desde el 2026-10-29 también corren `escanear.ps1` de punta a punta con un `ssh.exe` falso (compilado con `Add-Type`) que devuelve un escaneo dado, y comprueban que ninguna variable del script pisa un parámetro: en PowerShell los nombres de variable no distinguen mayúsculas, y una variable `topes` era el parámetro `[int]TopeS` (el resumen final falló así en el primer P-1).

`.gitattributes` deja los `*.sh` en LF también en el árbol de Windows: `escanear.ps1` manda el archivo tal cual y bash no correría un CRLF.

## El escaneo (protocolo P-1)

Lo corre el autor, en PowerShell, desde la raíz del repo, con las cámaras ya enchufadas a la Jetson:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/escanear.ps1 -Alias yahboom -Salida "Claude outputs/fases/007/escaneo/antes.txt" -TopeS 180
```

- Si la clave lleva frase de paso (P20), ssh la pide en la misma consola.
- Sale con 0 si llegaron las 12 secciones y la línea `ESCANEO_FIN`; con 2 si una entrada no vale (no conecta); con 3 si ssh falla o el escaneo queda a medias; con 124 si pasa de `-TopeS` (corta ssh). Lo recibido queda en `-Salida` en todos los casos.
- Si `nvpmodel -q` necesita root, el autor añade aparte la salida de `sudo nvpmodel -q`, en una sesión suya en la Jetson.

La salida trae nombres de máquina, IPs y la lista de procesos: va a `Claude outputs/` (fuera de git) y no se versiona tal cual.
