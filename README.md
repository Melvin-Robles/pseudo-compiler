# PseudoCompiler IDE

Este proyecto corresponde a la fase 3 del compilador de pseudocódigo. La aplicación se ejecuta de forma local y permite escribir o cargar un programa para generar su versión en Python o JavaScript.

## Antes de comenzar

Se Necesita tener instalados los siguientes programas:

- Python 3.10 o una versión más reciente
- Node.js 18 o una versión más reciente
- Git, solo si se desea clonar el proyecto desde un repo


## Comprobar las instalaciones

Abra PowerShell y ejecute:

```powershell
python --version
node --version
```

Si Windows no reconoce `python`, puede probar con:

```powershell
py --version
```


## Abrir el proyecto

Si se obtuvo el proyecto como archivo comprimido, se debe descompromir en una carpeta con permisos de escritura

Si es desde Git:

```powershell
git clone <URL_DEL_REPOSITORIO>
```


## Iniciar la aplicación

Desde la carpeta principal:

```powershell
python app.py
```

También puede usar:

```powershell
py app.py
```

Al iniciar, el navegador predeterminado debería abrir automáticamente esta dirección:

```text
http://127.0.0.1:8000
```

Si la pestaña no se abre por sí sola, copia la dirección y pégala manualmente en el navegador.

La ventana de PowerShell debe permanecer abierta mientras estés usando la aplicación. Para detener el servidor, presiona `Ctrl + C`.

## Si el puerto 8000 está ocupado

Puedes iniciar el servidor en otro puerto:

```powershell
python app.py --port 8765
```

En ese caso, abre:

```text
http://127.0.0.1:8765
```


## Problemas comunes

- Si `python` no se reconoce, usa `py app.py` o reinstala Python activando la opción `Add Python to PATH`.
- Si `node` no se reconoce, instala Node.js LTS y agrega Node al `PATH`.
- Si el puerto está ocupado, usa el puerto alternativo indicado arriba.
- Si la página no carga, confirma que la terminal siga mostrando que el servidor está disponible.
- Si no ves cambios recientes, cierra la pestaña, detén el servidor y vuelve a iniciar `python app.py`.
