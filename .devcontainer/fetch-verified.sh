#!/bin/bash
# Sourced by the create-time installers.

# Fetch into a destination only if the bytes match the expected digest.
fetch_verified() {  # url  expected-sha256  destination
    if curl -fsSL "$1" -o "$3.part" && echo "$2  $3.part" | sha256sum --check --status; then
        mv -f "$3.part" "$3"
    else
        rm -f "$3.part"
        return 1
    fi
}
