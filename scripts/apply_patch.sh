#!/usr/bin/env bash
# Usage: apply_patch.sh /path/to/file

file="$1"

if [ -z "$file" ]; then
    echo "No file specified"
    exit 1
fi

# Example rewrite: replace the word TODO with DONE
# (You can replace this with any rewrite command I generate for you)
sed -i 's/TODO/DONE/g' "$file"

echo "Patch applied to $file"
