# -*- coding: utf-8 -*-
"""
DIAGNOSTICO de distancias en Slicer. Toca un punto del hueso con el stylus y corre
esto. Imprime donde esta la punta virtual y a que distancia esta del STL, de la nube
y de cada marcador. Sirve para saber si el problema es el registro, el marcador
movido, o la calibracion del stylus.
"""
import numpy as np
import vtk
import slicer


def mat_to_world(node):
    M = vtk.vtkMatrix4x4()
    node.GetMatrixTransformToWorld(M)
    return np.array([[M.GetElement(i, j) for j in range(4)] for i in range(4)])


def world_points(model):
    pd = model.GetPolyData()
    n = pd.GetNumberOfPoints()
    pts = np.array([pd.GetPoint(i) for i in range(n)])
    par = model.GetParentTransformNode()
    Mw = mat_to_world(par) if par else np.eye(4)
    ph = np.c_[pts, np.ones(len(pts))]
    return (ph @ Mw.T)[:, :3]


# Punta del stylus en mundo
tip = slicer.util.getNode('StylusTip')
Mw = mat_to_world(tip.GetParentTransformNode())
tipw = Mw[:3, 3]
print("Tip (mundo):", np.round(tipw, 1))

# Distancia de la punta al STL y a la nube
bone = slicer.mrmlScene.GetFirstNodeByName('Bone')
if bone:
    bw = world_points(bone)
    print("Tip -> STL Bone:  %.1f mm" % np.min(np.linalg.norm(bw - tipw, axis=1)))
nube = slicer.mrmlScene.GetFirstNodeByName('NubeCapturada')
if nube:
    nw = world_points(nube)
    print("Tip -> Nube real: %.1f mm" % np.min(np.linalg.norm(nw - tipw, axis=1)))

# Origenes de los dos marcadores (deberian estar tan cerca como en la realidad)
for nm in ('Marker0ToTracker', 'DodecaedroToTracker'):
    nd = slicer.mrmlScene.GetFirstNodeByName(nm)
    o = mat_to_world(nd)[:3, 3]
    print(f"{nm} origen:", np.round(o, 1))
m0 = mat_to_world(slicer.util.getNode('Marker0ToTracker'))[:3, 3]
dd = mat_to_world(slicer.util.getNode('DodecaedroToTracker'))[:3, 3]
print("Distancia Marker0 <-> Dodecaedro: %.1f mm" % np.linalg.norm(m0 - dd))
print("(compara con la distancia fisica real entre el marcador del hueso y el dodecaedro)")
