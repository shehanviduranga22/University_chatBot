import os
import re
import time
import hashlib
import gzip
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
import chromadb
from sentence_transformers import SentenceTransformer


WEBSITE_URLS = [
    "https://www.sab.ac.lk/",
    "https://example1.com/",
    "https://example2.com/",
    "https://example3.com/",
    "https://example4.com/",
    "https://example5.com/",
    "https://example6.com/",
    "https://example7.com/",
    "https://example8.com/",
    "https://example9.com/",
    "https://example10.com/",
    "https://example11.com/",
    "https://example12.com/",
    "https://example13.com/",
    "https://example14.com/",
    "https://example15.com/",
    "https://example16.com/",
    "https://example17.com/",
    "https://example18.com/",
    "https://example19.com/",
]

MAX_PAGES_PER_SITE = int(os.getenv("MAX_PAGES_PER_SITE", "150"))
CHUNK_SIZE = int(os.getenv("WEB_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("WEB_CHUNK_OVERLAP", "200"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.5"))
MIN_TEXT_LENGTH = int(os.getenv("MIN_TEXT_LENGTH", "200"))

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

USER_AGENT = "UniversityKnowledgeBot/2.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vector_db")

client = chromadb.PersistentClient(path=DB_PATH)

collection = client.get_or_create_collection(
    name="university_documents",
    metadata={"hnsw:space": "cosine"}
)

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT
})

embedder = None


def clean_text(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url):
    url = urldefrag(url)[0]
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    return f"{scheme}://{netloc}{path}"


def domain(url):
    return urlparse(url).netloc.lower()


def remove_unwanted(soup):
    for tag_name in [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "canvas",
        "nav",
        "header",
        "footer",
        "aside",
        "form"
    ]:
        for tag in soup.find_all(tag_name):
            tag.decompose()


def extract_content(soup):
    remove_unwanted(soup)

    main = soup.find("main")
    if main:
        return main

    article = soup.find("article")
    if article:
        return article

    candidates = [
        soup.find(
            "div",
            class_=re.compile(
                r"content|main|article|page",
                re.I
            )
        ),
        soup.find(
            "div",
            id=re.compile(
                r"content|main|article|page",
                re.I
            )
        )
    ]

    for candidate in candidates:
        if candidate:
            return candidate

    return soup.body or soup


def extract_text(soup):
    container = extract_content(soup)
    parts = []

    for element in container.find_all([
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "td",
        "th"
    ]):
        text = clean_text(
            element.get_text(
                " ",
                strip=True
            )
        )

        if len(text) >= 3:
            parts.append(text)

    result = []
    previous = None

    for item in parts:
        if item != previous:
            result.append(item)
        previous = item

    return "\n".join(result)


def chunk_text(
    text,
    size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):
    paragraphs = [
        clean_text(x)
        for x in text.split("\n")
        if clean_text(x)
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue

        candidate = current + "\n" + paragraph

        if len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current.strip())

            overlap_text = current[
                max(0, len(current) - overlap):
            ]

            current = overlap_text + "\n" + paragraph

    if current.strip():
        chunks.append(current.strip())

    return chunks


def get_robots_parser(base_url):
    robots_url = urljoin(
        base_url,
        "/robots.txt"
    )

    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        response = session.get(
            robots_url,
            timeout=10
        )

        if response.status_code == 200:
            rp.parse(
                response.text.splitlines()
            )
            print("  robots.txt: loaded")
            return rp

        print("  robots.txt: not found")

    except requests.RequestException:
        print("  robots.txt: unavailable")

    return None


def allowed_by_robots(rp, url):
    if rp is None:
        return True

    try:
        return rp.can_fetch(
            USER_AGENT,
            url
        )
    except Exception:
        return True


def parse_sitemap(url):
    try:
        response = session.get(
            url,
            timeout=15
        )

        if response.status_code != 200:
            return []

        data = response.content

        if url.endswith(".gz"):
            data = gzip.decompress(data)

        root = ET.fromstring(data)

        namespace = {
            "sm": "http://www.sitemaps.org/schemas/sitemap/0.9"
        }

        urls = []

        if root.tag.endswith("sitemapindex"):
            for loc in root.findall(
                ".//sm:sitemap/sm:loc",
                namespace
            ):
                child = clean_text(loc.text or "")
                if child:
                    urls.extend(
                        parse_sitemap(child)
                    )

        else:
            for loc in root.findall(
                ".//sm:url/sm:loc",
                namespace
            ):
                page_url = clean_text(
                    loc.text or ""
                )

                if page_url:
                    urls.append(
                        normalize_url(page_url)
                    )

        return urls

    except Exception:
        return []


def get_sitemap_urls(base_url, rp):
    sitemap_urls = []

    if rp:
        try:
            sitemap_urls.extend(
                rp.site_maps() or []
            )
        except Exception:
            pass

    sitemap_urls.extend([
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
        urljoin(base_url, "/sitemap.xml.gz")
    ])

    found = set()

    for sitemap in sitemap_urls:
        if sitemap in found:
            continue

        found.add(sitemap)

        urls = parse_sitemap(sitemap)

        if urls:
            print(
                f"  Sitemap: {len(urls)} URLs found"
            )
            return urls

    print("  Sitemap: not found")
    return []


def is_html_url(url):
    extension = os.path.splitext(
        urlparse(url).path
    )[1].lower()

    blocked = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".zip",
        ".rar",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".mp4",
        ".mp3",
        ".avi",
        ".mov"
    }

    return extension not in blocked


def fetch_page(url):
    try:
        response = session.get(
            url,
            timeout=20
        )

        if response.status_code != 200:
            return None

        content_type = response.headers.get(
            "content-type",
            ""
        ).lower()

        if "text/html" not in content_type:
            return None

        return response.text

    except requests.RequestException:
        return None


def crawl_site(start_url):
    start_url = normalize_url(start_url)

    site_domain = domain(start_url)

    queue = deque()
    queued = set()
    visited = set()

    queue.append(start_url)
    queued.add(start_url)

    rp = get_robots_parser(start_url)

    sitemap_urls = get_sitemap_urls(
        start_url,
        rp
    )

    for sitemap_url in sitemap_urls:
        sitemap_url = normalize_url(sitemap_url)

        if (
            domain(sitemap_url) == site_domain
            and sitemap_url not in queued
        ):
            queue.append(sitemap_url)
            queued.add(sitemap_url)

    pages = []

    while queue and len(visited) < MAX_PAGES_PER_SITE:
        url = normalize_url(
            queue.popleft()
        )

        if url in visited:
            continue

        if domain(url) != site_domain:
            continue

        if not is_html_url(url):
            continue

        if not allowed_by_robots(rp, url):
            print("  Robots blocked:", url)
            continue

        visited.add(url)

        html = fetch_page(url)

        if not html:
            continue

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        title = (
            clean_text(
                soup.title.get_text()
            )
            if soup.title
            else url
        )

        text = extract_text(soup)

        if len(text) >= MIN_TEXT_LENGTH:
            pages.append({
                "url": url,
                "title": title,
                "text": text
            })

            print(
                f"  [{len(pages)}] {url}"
            )

        for anchor in soup.find_all(
            "a",
            href=True
        ):
            href = anchor.get("href")

            if not href:
                continue

            next_url = normalize_url(
                urljoin(url, href)
            )

            if (
                domain(next_url) != site_domain
                or not is_html_url(next_url)
            ):
                continue

            if (
                next_url not in visited
                and next_url not in queued
            ):
                queue.append(next_url)
                queued.add(next_url)

        time.sleep(REQUEST_DELAY)

    return pages


def content_hash(text):
    normalized = clean_text(text).lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def make_id(url, chunk_index):
    raw = f"{url}::{chunk_index}"

    return (
        "web_"
        + hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:32]
    )


def remove_duplicate_pages(pages):
    unique = []
    seen_urls = set()
    seen_content = set()

    for page in pages:
        url = normalize_url(
            page["url"]
        )

        page_hash = content_hash(
            page["text"]
        )

        if url in seen_urls:
            continue

        if page_hash in seen_content:
            continue

        seen_urls.add(url)
        seen_content.add(page_hash)

        page["url"] = url
        unique.append(page)

    return unique


def index_pages(pages):
    global embedder

    if embedder is None:
        print("\nLoading embedding model...")

        embedder = SentenceTransformer(
            EMBEDDING_MODEL
        )

        print("Embedding model loaded.")

    total_chunks = 0
    seen_chunk_hashes = set()

    for page_number, page in enumerate(
        pages,
        1
    ):
        chunks = chunk_text(
            page["text"]
        )

        chunks = [
            chunk
            for chunk in chunks
            if content_hash(chunk)
            not in seen_chunk_hashes
        ]

        if not chunks:
            continue

        for chunk in chunks:
            seen_chunk_hashes.add(
                content_hash(chunk)
            )

        print(
            f"Indexing {page_number}/{len(pages)}: "
            f"{page['title']}"
        )

        embeddings = embedder.encode(
            chunks,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

        ids = []
        documents = []
        metadatas = []

        for index, chunk in enumerate(chunks):
            ids.append(
                make_id(
                    page["url"],
                    index
                )
            )

            documents.append(chunk)

            metadatas.append({
                "source": "University Website",
                "title": page["title"],
                "url": page["url"],
                "type": "website",
                "chunk_index": index
            })

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        total_chunks += len(chunks)

        print(
            f"  Chunks: {len(chunks)}"
        )

    return total_chunks


def main():
    print("=" * 60)
    print("UNIVERSITY WEBSITE INGESTION")
    print("=" * 60)

    all_pages = []

    for number, website in enumerate(
        WEBSITE_URLS,
        1
    ):
        print("\n" + "-" * 60)
        print(
            f"Website {number}/{len(WEBSITE_URLS)}"
        )
        print(website)
        print("-" * 60)

        try:
            pages = crawl_site(
                website
            )

            print(
                f"Collected: {len(pages)} pages"
            )

            all_pages.extend(pages)

        except Exception as error:
            print(
                "Website failed:",
                error
            )

    print("\n" + "=" * 60)
    print("REMOVING DUPLICATES")
    print("=" * 60)

    before = len(all_pages)

    all_pages = remove_duplicate_pages(
        all_pages
    )

    print(
        "Before:",
        before
    )

    print(
        "After:",
        len(all_pages)
    )

    if not all_pages:
        print("No pages collected.")
        return

    print("\n" + "=" * 60)
    print("INDEXING")
    print("=" * 60)

    total_chunks = index_pages(
        all_pages
    )

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)

    print(
        "Websites:",
        len(WEBSITE_URLS)
    )

    print(
        "Unique pages:",
        len(all_pages)
    )

    print(
        "New chunks:",
        total_chunks
    )

    print(
        "ChromaDB documents:",
        collection.count()
    )

    print(
        "Database:",
        DB_PATH
    )

    print("=" * 60)


if __name__ == "__main__":
    main()

