# -*- coding: utf-8 -*-
"""
DIAGNOSTICO: carga la nube TSDF (la que se uso para registrar) en el frame del
marcador, para ver si el STL 'Bone' (via BoneToMarker0) cae sobre ella.

- Si Bone (amarillo) y NubeCapturada (azul) COINCIDEN -> la inyeccion y el registro
  estan bien; el desfase al tocar el hueso fisico es porque el MARCADOR se movio
  respecto al hueso desde la captura (hay que re-capturar + re-registrar).
- Si NO coinciden -> el problema es la inyeccion (unidades/convencion) y lo arreglamos.

Ejecutar en la consola Python de Slicer.
"""
import vtk
import slicer

# La MALLA TSDF de la misma sesion del registro (esta en metros, frame del marcador)
RUTA_MALLA = r"C:\Dev\Dr.Milton\PoyectoNavegacion\femto_pruebas\nubes\tsdf_20260616_223759_malla.ply"

m = slicer.mrmlScene.GetFirstNodeByName('NubeCapturada')
if m is None:
    m = slicer.util.loadModel(RUTA_MALLA)
    m.SetName('NubeCapturada')

# Transform de escala metros->mm
esc = slicer.mrmlScene.GetFirstNodeByName('EscalaMM')
if esc is None:
    esc = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'EscalaMM')
vm = vtk.vtkMatrix4x4()
vm.Identity()
# metros->mm Y compensar el flip LPS->RAS que loadModel aplica al .ply:
# escala = diag(-1000, -1000, 1000) -> deja la nube en coords reales del marcador
vm.SetElement(0, 0, -1000.0)
vm.SetElement(1, 1, -1000.0)
vm.SetElement(2, 2, 1000.0)
esc.SetMatrixTransformToParent(vm)

# Anidar: NubeCapturada -> EscalaMM -> Marker0ToTracker  (mismo frame que Bone)
marker0 = slicer.mrmlScene.GetFirstNodeByName('Marker0ToTracker')
if marker0 is not None:
    esc.SetAndObserveTransformNodeID(marker0.GetID())
m.SetAndObserveTransformNodeID(esc.GetID())

# Color azul semitransparente para distinguir del Bone (amarillo)
d = m.GetDisplayNode()
d.SetColor(0.1, 0.4, 1.0)
d.SetOpacity(0.5)

print("NubeCapturada (azul) cargada en el frame del marcador, junto a Bone (amarillo).")
print("Ambos estan bajo Marker0ToTracker, asi que se mueven juntos con el marcador.")
print(">> Si AZUL y AMARILLO coinciden: inyeccion/registro OK, el marcador se movio")
print("   respecto al hueso fisico -> re-capturar (08) + re-registrar (06).")
print(">> Si NO coinciden: es la inyeccion -> avisame y revisamos unidades/convencion.")
