"""Lo que corre en la Jetson Orin Nano y lo que la gobierna desde el PC (meta 007).

- `guardian.py`: el guardian de la cuenta `navagente` (fase 2). En la Jetson corre con el
  python3 del sistema (`-I`), solo biblioteca estandar y Python >= 3.8; aqui se importa para
  probar su logica sin Jetson.
- `sonda_privilegios.py`: lo que haria un codigo del agente que intentara salirse (fase 2).
- `tars_malos.py`: los tar que `wip recibir` tiene que negar, para la suite y probar_barrera.ps1.
- Los scripts para el autor (`instalar_guardian.sh`, `desinstalar_guardian.sh`, `probar_barrera.ps1`)
  y el escaneo (`escanear_jetson.sh`, `escanear.ps1`) no son modulos.
"""
