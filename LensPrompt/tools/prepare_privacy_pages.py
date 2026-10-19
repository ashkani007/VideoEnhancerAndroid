"""Package only the policy webpage for GitHub Pages; no Android build required."""
from html.parser import HTMLParser
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
SITE_HOSTING = "This public policy page is hosted using OpenAI Sites infrastructure and its hosting providers."
PAGES_HOSTING = "This public policy page is hosted on GitHub Pages by GitHub and its hosting providers."


class PolicyCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = set()
        self.scripts = 0
        self.viewport = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            self.sections.add(attrs.get("id"))
        if tag == "script":
            self.scripts += 1
        if tag == "meta" and attrs.get("name") == "viewport":
            self.viewport = True


def prepare(destination):
    page = (ROOT / "docs/privacy-policy.html").read_text()
    if page.count(SITE_HOSTING) != 1:
        raise ValueError("Review policy hosting disclosure before packaging.")
    page = page.replace(SITE_HOSTING, PAGES_HOSTING)
    check = PolicyCheck()
    check.feed(page)
    if check.sections != {f"section-{n}" for n in range(1, 14)} or check.scripts or not check.viewport:
        raise ValueError("Policy is missing sections/mobile metadata or contains scripts.")
    for expected in ["com.lensprompt.app", "Supernova studio", "mailto:abbasian7iraj@gmail.com"]:
        if expected not in page:
            raise ValueError(f"Missing policy identity/contact: {expected}")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "index.html").write_text(page)
    (destination / ".nojekyll").write_text("")
    print(f"Prepared policy-only Pages artifact at {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
