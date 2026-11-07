"""Serve a directory over HTTP the way GitHub serves a dnf repository's two parts.

`ci.yml`'s `dnf-repo` job runs this for `ci/dnf-repo-test.sh` to test the
repository `packaging/dnf-repo.sh` builds. Files under ROOT are served as they
are, as Pages serves the metadata. A request for ``/releases/download/TAG/FILE``
gets a 302 to ``/assets/TAG/FILE``, as a GitHub Release download redirects to
the host that stores its assets.

Usage: ``dnf_repo_server.py ROOT PORT``. Standard library only.
"""

import functools
import http.server
import sys
from http import HTTPStatus

_RELEASES = "/releases/download/"


class _Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith(_RELEASES):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/assets/" + self.path.removeprefix(_RELEASES))
            self.end_headers()
        else:
            super().do_GET()

    def do_HEAD(self) -> None:
        if self.path.startswith(_RELEASES):
            self.do_GET()
        else:
            super().do_HEAD()


def main(argv: list[str]) -> None:
    """Serve ROOT on PORT until killed.

    Args:
        argv: ROOT and PORT.
    """
    root, port = argv
    handler = functools.partial(_Handler, directory=root)
    http.server.ThreadingHTTPServer(("127.0.0.1", int(port)), handler).serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
