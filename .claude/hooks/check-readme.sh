#!/usr/bin/env bash
# PostToolUse hook — rappel de mise à jour README si un fichier clé est modifié

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ -z "$FILE_PATH" ]] && exit 0

# Fichiers dont les changements doivent se refléter dans le README
KEY_FILES=(
  "manifest.json"
  "services.yaml"
  "config_flow.py"
  "__init__.py"
  "coordinator.py"
  "sensor.py"
  "printer-maintenance-card.js"
)

for key in "${KEY_FILES[@]}"; do
  if [[ "$FILE_PATH" == *"$key" ]]; then
    echo "README_REMINDER: Le fichier '$key' a été modifié. Vérifie si le README (version, services, config flow, fonctionnalités) doit être mis à jour."
    exit 0
  fi
done

exit 0
