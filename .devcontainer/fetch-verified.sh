#!/bin/bash
# Sourced by the create-time installers.

# Fetch into a destination only if the bytes match the expected digest.
fetch_verified() {  # url  expected-sha256  destination
    curl -fsSL "$1" -o "$3" && echo "$2  $3" | sha256sum --check --status
}
