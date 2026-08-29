from admin_console import UNIFIED_ADMIN_HTML as h
checks={
'nav_sections': all(x in h for x in ['Memoria','Documentos / RAG','Diccionario','Reglas empresariales','Reglas analíticas','Feedback','Trazabilidad','Historial','Auditoría']),
'state_badges': all(x in h for x in ['VALIDADO','PROPUESTO','RECHAZADO','OBSOLETO']),
'admin_actions': all(x in h for x in ['validateRule','rejectRule','obsoleteRule','validateSem','validateFeedback']),
'conflict_confirmation':'reemplazar conflictos validados' in h,
'trace_explanation':'explainTrace' in h,
}
for k,v in checks.items(): assert v,k; print('PASS',k)
print(f'{len(checks)}/{len(checks)} PASS R10.10 UI')
