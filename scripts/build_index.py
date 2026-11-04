"""Build a PEP 503 "simple" package index from the GitHub Releases of this repo.

Files stay attached to the releases; the index only links to them. Output is a
static site (default ``site/``) deployed to GitHub Pages by the release
workflow, giving a fixed URL such as
``https://<owner>.github.io/<repo>/simple/``.

Only the PEP 503 HTML API is produced. PEP 691 (JSON) needs Accept-header
content negotiation, which static hosting cannot do; uv and pip read the HTML.

Needs the ``gh`` CLI (authenticated via GH_TOKEN) and the standard library only.
Usage: python scripts/build_index.py [outdir]
"""

import html
import json
import re
import subprocess
import sys
from pathlib import Path

DIST_SUFFIXES = (".whl", ".tar.gz")


def gh_api(path):
    out = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        check=True, capture_output=True, text=True,
    ).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page]


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main(outdir):
    outdir = Path(outdir)
    releases = gh_api("repos/{owner}/{repo}/releases")
    packages = {}  # normalized name -> [(filename, url)]
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        tag = rel["tag_name"]
        if "-v" not in tag:
            continue
        pkg = normalize(tag.split("-v", 1)[0])
        for asset in rel["assets"]:
            if asset["name"].endswith(DIST_SUFFIXES):
                packages.setdefault(pkg, []).append(
                    (asset["name"], asset["browser_download_url"])
                )

    simple = outdir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    (outdir / ".nojekyll").touch()

    def page(title, links):
        body = "\n".join(f'    <a href="{html.escape(u)}">{html.escape(t)}</a><br>' for t, u in links)
        return (
            f"<!DOCTYPE html>\n<html>\n  <head><meta name=\"pypi:repository-version\" "
            f"content=\"1.0\"><title>{html.escape(title)}</title></head>\n"
            f"  <body>\n{body}\n  </body>\n</html>\n"
        )

    (simple / "index.html").write_text(
        page("Simple index", [(p, f"{p}/") for p in sorted(packages)]), encoding="utf-8"
    )
    for pkg, files in packages.items():
        d = simple / pkg
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(
            page(f"Links for {pkg}", sorted(files)), encoding="utf-8"
        )
    print(f"Indexed {sum(map(len, packages.values()))} files for {sorted(packages)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site")
