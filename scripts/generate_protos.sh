#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

rm -rf amino cosmos cosmos_proto gogoproto predictionmarket

protoc \
  -I proto \
  --python_out=. \
  $(find proto -name '*.proto' | sort)

while IFS= read -r package_dir; do
  touch "$package_dir/__init__.py"
done < <(find amino cosmos cosmos_proto gogoproto predictionmarket -type d | sort)
