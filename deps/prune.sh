#!/usr/bin/env bash

set -eo pipefail

{
  read -r
  keep=( -name "$REPLY" ) # no `-o` before the first one.
  while read -r; do
    keep+=( -o -wholename "./$REPLY" )
  done
} < required.txt

# remove files/links not present in the list
find . -type f ! \( "${keep[@]}" \) -delete
find . -type l ! \( "${keep[@]}" \) -delete

# remove empty directories
find . -type d -empty -delete
