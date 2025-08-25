#!/bin/bash
cd /home/kavia/workspace/code-generation/cashapp---autoconfig-3585-3779/APIGateway
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

