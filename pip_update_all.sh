#!/bin/bash
# pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1  | xargs -n1 pip install -U
pip list --outdated | tail -n +3 | awk '{print $1}' | xargs -i pip install {} --upgrade