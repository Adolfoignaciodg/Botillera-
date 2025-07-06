# Botillera-

Este código crea un Dashboard interactivo de ventas usando Streamlit, una herramienta para crear aplicaciones web de forma sencilla con Python. El propósito principal es analizar y visualizar datos de ventas y compararlos con un catálogo de productos para detectar posibles errores o inconsistencias.

1. Configuración inicial y carga de archivos
Configuración de la página:
Se define el título y el diseño general del dashboard (ancho completo) para mejorar la visualización.

Carga del archivo de configuración JSON:
El dashboard espera un archivo report.json que contiene las URLs de los datos de ventas (CSV) y el catálogo de productos (Excel).
Esto permite que el dashboard funcione con datos actualizados sin cambiar el código, solo modificando ese JSON.

Carga de datos CSV y Excel:
Se leen los datos de ventas (CSV) y catálogo (Excel) desde las URLs indicadas en el JSON.
Se validan para asegurarse de que los archivos se carguen correctamente y que tengan las columnas necesarias.

2. Preparación y limpieza de los datos
Detección automática de columnas clave:
Como los archivos pueden venir con nombres de columnas variables, se buscan automáticamente las columnas importantes (por ejemplo: nombre de producto, sucursal, fecha, cantidad, subtotal, etc.)
Esto hace el código más robusto y adaptable a diferentes fuentes.

Validaciones básicas:
Si faltan columnas esenciales como sucursal, producto o mes, el dashboard muestra un error y no continúa, para evitar mostrar datos erróneos.

Transformaciones:

Se convierten las columnas numéricas (cantidad, precio, costos) a números para poder hacer sumas y gráficos.

Se convierte la columna de fecha a formato fecha real para poder filtrar y mostrar datos por días, meses y años.

Se extraen columnas auxiliares como año, mes (número y nombre), día, que se usan para filtros y agrupaciones.

3. Interfaz de filtros (Sidebar)
El usuario puede filtrar la información por:

Sucursal (tienda o punto de venta)

Tipo de producto o servicio (si existe esta clasificación)

Producto específico

Mes

Esto permite que el dashboard muestre datos solo del segmento seleccionado para análisis más detallados.

4. Aplicación de filtros y preparación de datos filtrados
Se aplican los filtros seleccionados por el usuario a los datos originales para obtener un subconjunto limpio y relevante para análisis.

Si los filtros no arrojan datos, se avisa y no se muestra información vacía.

5. Visualización principal con pestañas
El dashboard tiene 4 pestañas principales:

Pestaña 1: Resumen y detalle
Muestra métricas clave sumadas: cantidades, subtotales, costos, márgenes, impuestos.

Muestra tablas con cantidades vendidas por producto.

Permite ver detalle diario de ventas, y gráficos de evolución temporal de ventas por producto.

Se adapta si se elige un producto o todos los productos.

Pestaña 2: Análisis ABC de productos
Realiza un análisis ABC basado en el subtotal neto vendido.

Clasifica productos en categorías A, B y C según su contribución acumulada a las ventas (por ejemplo, 70% ventas = A, siguiente 20% = B, resto = C).

Muestra tabla con esta clasificación y un gráfico de barras coloreado para visualización rápida.

Pestaña 3: Detalle por día y categoría
Permite seleccionar año, mes y día para ver ventas específicas de esa fecha.

Muestra detalle segmentado por categoría de producto (si existe) y producto.

Pestaña 4: Productos repetidos y no registrados (control de calidad)
Carga el catálogo de productos.

Detecta productos duplicados en el catálogo considerando combinación de nombre + variante + SKU (si están disponibles). Esto ayuda a mantener el catálogo limpio.

Detecta SKUs duplicados, que no deberían repetirse.

Compara productos vendidos con productos del catálogo:

Lista productos vendidos que no están en el catálogo (posibles errores o ventas no registradas).

Lista SKUs vendidos que no están en el catálogo.

Todo esto ayuda a controlar la calidad de los datos y detectar errores en ventas o inventario.

6. Funciones auxiliares y detalles técnicos
Normalización de nombres y SKUs:
Para comparar correctamente, se convierten los textos a minúsculas, se eliminan espacios al inicio y fin para evitar falsos negativos en las comparaciones.

Uso de cache:
Para mejorar el rendimiento, la carga de archivos y cálculos pesados se cachean, evitando que se repitan innecesariamente.

Visualización con Altair:
Se usan gráficos de líneas y barras con buena interacción (tooltips, filtros) para facilitar la exploración de datos.

7. Resumen general del flujo del programa
Carga configuración y archivos (ventas y catálogo).

Valida y limpia datos, detecta columnas clave.

Muestra filtros para segmentar análisis.

Aplica filtros y prepara datos filtrados.

Muestra métricas, tablas y gráficos en pestañas para análisis general, ABC, detalle por fecha y control de calidad del catálogo.

Permite detectar inconsistencias entre ventas y catálogo para mejorar gestión y evitar errores.
