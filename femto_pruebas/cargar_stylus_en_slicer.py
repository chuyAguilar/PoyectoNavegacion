# -*- coding: utf-8 -*-
"""
CARGAR STYLUS (pivote + StylusTip) EN 3D SLICER  (iter 5)

Ejecutar en la CONSOLA PYTHON de 3D Slicer (Ctrl+3), con tracker.py corriendo
(debe existir el nodo 'DodecaedroToTracker').

Monta la cadena minima para VER la punta del stylus:
    StylusTip -> StylusTipToDodecaedro -> DodecaedroToTracker

No hace falta Transform Processor ni DodecaedroToMarker0 para la coincidencia
visual: Bone y StylusTip quedan ambos en el frame del tracker, asi que si el
registro (BoneToMarker0) es correcto, al tocar el hueso fisico la punta virtual
cae sobre la superficie del STL.

Calibracion de pivote: StylusTipToDodecaedro_viejo_dock.npy (stylus VIEJO + dock,
geometria reference_dodecaedro_calibrado.txt, RMS 0.787 mm). YA esta en mm.
Si usas OTRO stylus, cambia RUTA_PIVOTE por la calibracion correcta.
"""
import numpy as np
import vtk
import slicer

# ===================== EDITA SI USAS OTRO STYLUS =====================
RUTA_PIVOTE = r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\iter4\data\StylusTipToDodecaedro_viejo_dock.npy"
# =====================================================================

M = np.load(RUTA_PIVOTE).astype(float)   # ya en mm
print("=== StylusTipToDodecaedro (mm) ===")
print(np.array_str(M, precision=3, suppress_small=True))
print(f"Offset punta: [{M[0,3]:+.2f}, {M[1,3]:+.2f}, {M[2,3]:+.2f}] mm "
      f"(magnitud {np.linalg.norm(M[:3,3]):.2f} mm)")

# 1. Nodo StylusTipToDodecaedro
t = slicer.mrmlScene.GetFirstNodeByName('StylusTipToDodecaedro')
if t is None:
    t = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'StylusTipToDodecaedro')
vm = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        vm.SetElement(i, j, float(M[i, j]))
t.SetMatrixTransformToParent(vm)

# 2. Anidar bajo DodecaedroToTracker
dod = slicer.mrmlScene.GetFirstNodeByName('DodecaedroToTracker')
if dod is None:
    print("AVISO: no existe 'DodecaedroToTracker'. Corre tracker.py y verifica que "
          "el dodecaedro se detecte (3+ markers), luego re-ejecuta.")
else:
    t.SetAndObserveTransformNodeID(dod.GetID())
    print("StylusTipToDodecaedro anidado bajo DodecaedroToTracker.")

# 3. StylusTip (fiducial en el origen del frame de la punta)
tip = slicer.mrmlScene.GetFirstNodeByName('StylusTip')
if tip is None:
    tip = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', 'StylusTip')
    tip.AddControlPoint(0, 0, 0, 'Tip')
    tip.GetDisplayNode().SetGlyphScale(2.5)
    tip.GetDisplayNode().SetSelectedColor(1, 0, 0)
tip.SetAndObserveTransformNodeID(t.GetID())
print("StylusTip (punto rojo) anidado bajo StylusTipToDodecaedro.")

print("\nListo. Toca el hueso fisico con la punta del stylus:")
print("  - El punto rojo 'StylusTip' debe caer sobre la superficie del STL 'Bone'.")
print("  - Si cae sobre el hueso -> el registro por superficie es correcto.")
print("  - Si cae al lado/desplazado de forma consistente -> hay un offset (revisar).")
