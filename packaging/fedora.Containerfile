# The Fedora image .github/workflows/rpm.yml and ci.yml's dnf-repo job run in. It lives here
# because Dependabot's docker ecosystem updates a Containerfile's FROM line but not a
# workflow's container image (dependabot/dependabot-core#5819).
FROM fedora:45@sha256:a7d72ba2745b100a3351087472e5ee7b2450af7cf331e7673007e3817612839c
