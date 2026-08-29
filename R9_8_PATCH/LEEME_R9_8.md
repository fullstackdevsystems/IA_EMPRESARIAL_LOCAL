# IA Empresarial Local R9.8

R9.8 agrega exportación Excel XLSX real directamente desde el dashboard.

- Exporta exactamente los registros de la selección filtrada actual.
- Genera un archivo `.xlsx` válido mediante Open XML + ZIP local.
- No usa CDN, internet ni librerías JavaScript externas.
- Conserva exportación CSV.
- Conserva la corrección R9.7.1 de `Todos` en filtros múltiples.
- El plan de ejecución marca `excel_export` como `ready` cuando el prompt lo solicita.
- La única capacidad del prompt de prueba que continúa explícitamente no soportada en esta etapa es la consulta en lenguaje natural dentro del propio HTML.
