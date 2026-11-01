# Third-party licenses (8-Ball console)

The console's own code follows the license of this repository. At the time of writing the repository has
no top-level LICENSE file; the maintainers choose it. Nothing below is vendored into this folder: the
Python packages are installed from PyPI with the pinned hashes in `requirements.txt`, and ttyd is an
optional, separately downloaded binary.

| Component | Version | License | How it is used |
|---|---|---|---|
| fastapi | 0.162.0 | MIT | HTTP API framework |
| starlette | 1.10.0 | BSD-3-Clause | ASGI toolkit (fastapi dependency) |
| pydantic | 2.14.2 | MIT | fastapi dependency |
| pydantic-core | 2.50.2 | MIT | pydantic dependency |
| annotated-types | 0.8.0 | MIT | pydantic dependency |
| annotated-doc | 0.0.5 | MIT | fastapi dependency |
| typing-extensions | 4.16.0 | PSF-2.0 | typing backports |
| typing-inspection | 0.4.4 | MIT | pydantic dependency |
| opentelemetry-api | 1.45.2 | Apache-2.0 | fastapi dependency (no exporter is configured) |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| click | 8.5.0 | BSD-3-Clause | uvicorn dependency |
| h11 | 0.16.0 | MIT | HTTP/1.1 (uvicorn, httpcore) |
| anyio | 4.15.1 | MIT | async I/O |
| httpx | 0.28.1 | BSD-3-Clause | native Ollama REST client |
| httpcore | 1.0.9 | BSD-3-Clause | httpx dependency |
| certifi | 2026.10.23 | MPL-2.0 | CA bundle (httpx dependency) |
| idna | 3.20 | BSD-3-Clause | httpx dependency |
| ttyd (optional) | 1.7.7 | MIT | read-only terminal view of job logs; bundles xterm.js (MIT) and libwebsockets (MIT) |

The UI (`eightball_console/static/`) is plain HTML, CSS and JavaScript with no third-party code.
Ollama itself is not part of this app; the console only calls its documented REST API.
