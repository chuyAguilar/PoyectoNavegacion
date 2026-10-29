#!/bin/sh
# revisar_peticiones.sh - la regla de ADR-034, en un solo sitio.
#
# Lee de la entrada estandar lineas "<estado><TAB><ruta>", como las que da
# "git diff --name-status --no-renames". Sale 0 si todas son peticiones
# nuevas: estado A y ruta "peticiones/<nombre>.md" (ni README.md ni
# _plantilla.md, ni subcarpetas). Si alguna no lo es, escribe una linea en
# espanol por cada ruta rechazada y sale 1. Sin entrada, sale 0.
#
# Lo usan pre-commit y pre-push. Los mensajes van sin tildes a proposito:
# la consola de PowerShell 5.1 no siempre muestra bien el UTF-8 que
# imprime un hook.

tab=$(printf '\t')
rc=0

while IFS="$tab" read -r estado ruta; do
    [ -z "$estado" ] && continue
    if [ -z "$ruta" ]; then
        echo "linea sin ruta: '$estado'"
        rc=1
        continue
    fi
    case "$ruta" in
        peticiones/README.md|peticiones/_plantilla.md)
            echo "$ruta: ese archivo es del proyecto, no una peticion; solo lo cambia el autor"
            rc=1
            ;;
        peticiones/*/*)
            echo "$ruta: una peticion es un archivo .md directamente en peticiones/, sin subcarpetas"
            rc=1
            ;;
        peticiones/*.md)
            case "$estado" in
                A) ;;
                *)
                    echo "$ruta: una peticion enviada no se modifica ni se borra; escribe otra que la cite"
                    rc=1
                    ;;
            esac
            ;;
        peticiones/*)
            echo "$ruta: una peticion es un archivo .md en peticiones/ (ver peticiones/README.md)"
            rc=1
            ;;
        *)
            echo "$ruta: solo se pueden enviar peticiones nuevas en peticiones/; lo demas lo cambia el autor"
            rc=1
            ;;
    esac
done

exit $rc
