# R10.12 — Dataset controlado para fine-tuning

Fuentes: reglas VALIDADO, definiciones semánticas VALIDADO y memorias activas/confirmadas con sensibilidad normal.
Exclusiones: PROPUESTO, RECHAZADO, OBSOLETO, pending, secretos, credenciales, emails, teléfonos y duplicados.
Flujo: fuente validada → candidato → revisión admin → APPROVED/REJECTED → split determinista train/validation → export JSONL.
Garantía: `training_executed=false`. Esta fase no invoca Ollama, LoRA, QLoRA ni frameworks de entrenamiento.
