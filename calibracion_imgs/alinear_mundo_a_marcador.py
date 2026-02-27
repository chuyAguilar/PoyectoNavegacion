
"""
Script de Alineación 1:1 (Versión 2 - ROBUSTA)

Objetivo:
    Mover el mundo virtual (Modelos + Volúmenes) para que el marcador virtual
    coincida con el origen (0,0,0) de la escena.

Mejoras V2:
    - Limpia registros anteriores para evitar duplicados.
    - Maneja mejor la jerarquía de nodos.
    - Ofrece opciones de depuración.
"""

import slicer
import vtk

def alinear_v2(nombre_marcador="ArUco_Columna", solo_traslacion=False):
    print("="*50)
    print("INICIANDO ALINEACIÓN V2")
    print("="*50)

    # 1. Buscar el marcador
    try:
        nodo_marcador = slicer.util.getNode(nombre_marcador)
    except slicer.util.MRMLNodeNotFoundException:
        print(f"❌ ERROR: No encuentro el nodo '{nombre_marcador}'")
        return

    # 2. Calcular la matriz del marcador en coordenadas MUNDIALES
    #    (Independientemente de si está dentro de otros transforms)
    matriz_marcador_mundo = vtk.vtkMatrix4x4()
    
    if isinstance(nodo_marcador, slicer.vtkMRMLTransformNode):
        nodo_marcador.GetMatrixTransformToWorld(matriz_marcador_mundo)
    elif isinstance(nodo_marcador, slicer.vtkMRMLModelNode):
        # Para modelos, es más complejo si tienen transforms.
        # Asumiremos que tienen un transform padre o están en la escena.
        transform_id = nodo_marcador.GetTransformNodeID()
        if transform_id:
            nodo_padre = slicer.mrmlScene.GetNodeByID(transform_id)
            nodo_padre.GetMatrixTransformToWorld(matriz_marcador_mundo)
        else:
            # Si no tiene padre transform, su matrix mundo es identidad (está en 0,0,0)
            # A MENOS que tenga puntos desplazados. Usamos centroide.
            print("⚠️ Modelo sin Transform Padre. Usando centroide...")
            center = [0.0]*3
            if nodo_marcador.GetPolyData():
                nodo_marcador.GetPolyData().GetCenter(center)
                matriz_marcador_mundo.SetElement(0, 3, center[0])
                matriz_marcador_mundo.SetElement(1, 3, center[1])
                matriz_marcador_mundo.SetElement(2, 3, center[2])
            else:
                print("❌ Modelo sin datos geométricos.")
                return

    # Imprimir para debug
    x = matriz_marcador_mundo.GetElement(0, 3)
    y = matriz_marcador_mundo.GetElement(1, 3)
    z = matriz_marcador_mundo.GetElement(2, 3)
    print(f"📍 Posición actual del marcador: ({x:.2f}, {y:.2f}, {z:.2f})")

    # 3. Preparar la matriz inversa (World -> Reference)
    matriz_registro = vtk.vtkMatrix4x4()
    matriz_registro.DeepCopy(matriz_marcador_mundo)
    matriz_registro.Invert()
    
    if solo_traslacion:
        # Si solo queremos mover XYZ pero no rotar (para evitar giros locos)
        # Reseteamos la rotación a la identidad
        # (Esto es complejo porque la inversa ya mezcló rotación y traslación)
        # Enfoque simple: La traslación inversa es -P (si no hay rotación)
        print("ℹ️ Modo: Solo Traslación activado")
        matriz_registro.Identity()
        matriz_registro.SetElement(0, 3, -x)
        matriz_registro.SetElement(1, 3, -y)
        matriz_registro.SetElement(2, 3, -z)

    # 4. Crear/Actualizar el nodo de Transformación de Registro
    nombre_transform = "Registro_Mundo_A_Marcador"
    nodo_registro = slicer.mrmlScene.GetFirstNodeByName(nombre_transform)
    if not nodo_registro:
        nodo_registro = slicer.vtkMRMLLinearTransformNode()
        nodo_registro.SetName(nombre_transform)
        slicer.mrmlScene.AddNode(nodo_registro)
    
    nodo_registro.SetMatrixTransformToParent(matriz_registro)
    print(f"✅ Transformación '{nombre_transform}' actualizada.")

    # 5. Mover objetos bajo esta transformación
    #    ESTRATEGIA SEGURA: Mover solo carpetas (SubjectHierarchy) o cosas especificas.
    #    Para evitar mover el marcador (que se movería doble), lo sacamos primero.
    
    # Asegurar que el marcador NO esté bajo el registro
    nodo_marcador.SetAndObserveTransformNodeID(None) 
    
    # Mover 'Segmentation'
    try:
        seg = slicer.util.getNode('Segmentation')
        seg.SetAndObserveTransformNodeID(nodo_registro.GetID())
        print("   -> 'Segmentation' movido.")
    except:
        pass
        
    # Mover Volúmenes (si hay alguno visible)
    vols = slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')
    for vol in vols:
        if vol.GetDisplayNode() and vol.GetDisplayNode().GetVisibility():
            vol.SetAndObserveTransformNodeID(nodo_registro.GetID())
            print(f"   -> Volumen '{vol.GetName()}' movido.")

    # Mover Modelos (opcional, cuidado con duplicados)
    # models = slicer.util.getNodesByClass('vtkMRMLModelNode')
    # ... aqui hay riesgo de mover cosas de la UI ...
    
    print("\n✅ ALINEACIÓN COMPLETADA")
    print("   Verifica que el marcador ArUco Columna ahora coincida con el origen (cruces en Slicer)")

# Ejecutar
alinear_v2(solo_traslacion=False) # Cambia a True si la rotación sale mal
