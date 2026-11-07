---
description: Set up this template for your project
---

# Onboard

Set up this repository for a new project by applying `docs/onboard.md`. That page says what
changes and in what order; this command says how to run it with the user.

## Process

### 1. Prerequisites

Check `gh auth status`. If not authenticated, tell the user to run `gh auth login` before continuing: the GitHub settings steps use `gh`.

### 2. Interview

Read `docs/onboard.md`. Ask the user its Decide list in a single message. Say that the conduct and security contacts are published, so they should give addresses they are willing to publish.

### 3. Confirm

Summarize the answers and the changes you will make, the files you will delete included. Wait for the user to confirm before proceeding.

### 4. Apply

Work through `docs/onboard.md` in order, from Decide through GitHub settings: carry out what each Decide item says to do with its answer, then each section after it. Use only values the user gave: never invent one. Leave the steps that can't run from inside the container, such as removing a container or a volume for a declined Feature, for the report.

### 5. Report

List the GitHub settings you could not apply, for the user to set. Name **private vulnerability reporting** (Settings > Security) first: until it is on, the advisory form `.github/SECURITY.md` sends every reporter to does not exist. Then give the steps you left because they can't run inside the container, in their order, ending with the rebuild.

### 6. Clean up

Do the page's Finish steps, which delete this command file with the page.
