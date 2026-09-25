"""Preserve public evidence for the WBS 2.3 review; no account or key output."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.links = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('name')
    p.add_argument('url')
    args = p.parse_args()
    if urlsplit(args.url).hostname not in ('www.daejeon.go.kr', 'daejeon.go.kr'):
        p.error('Only public Daejeon government sources are allowed.')
    root = Path('tmp/policy_research_20260925/sources')
    root.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(args.url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
        data = r.read()
        final_url = r.url
        content_type = r.headers.get('Content-Type', '')
    ext = '.html' if 'html' in content_type else '.bin'
    file = root / (args.name + ext)
    file.write_bytes(data)
    meta = dict(url=args.url, final_url=final_url, checked_at=datetime.now(timezone.utc).isoformat(),
                content_type=content_type, sha256=hashlib.sha256(data).hexdigest(), file=str(file))
    if ext == '.html':
        doc = Extract()
        doc.feed(data.decode('utf-8', errors='replace'))
        (root / (args.name + '.txt')).write_text('\n'.join(doc.text), encoding='utf-8')
        meta['links'] = list(dict.fromkeys(urljoin(final_url, x) for x in doc.links))
    (root / (args.name + '.json')).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in meta.items() if k != 'links'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
