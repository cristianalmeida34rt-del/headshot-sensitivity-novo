#!/usr/bin/env python3
"""Sincroniza as três notícias oficiais mais recentes do Free Fire em português.

A fonte é somente o HTML público de https://ff.garena.com/pt/news/.
Não usa APIs não documentadas, chaves, tradução automática ou conteúdo de terceiros.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://ff.garena.com/pt/news/"
OFFICIAL_HOST = "ff.garena.com"
NEWS_FILE = ROOT / "app/src/main/assets/news_data.js"
GRADLE_FILE = ROOT / "app/build.gradle"
INDEX_FILE = ROOT / "app/src/main/assets/index.html"
LATEST_COUNT = 3
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
USER_AGENT = "HeadshotSensitivity-OfficialNewsSync/1.0"
FALLBACK_SUMMARY = "Confira os detalhes na publicação oficial da Garena."


class NewsSyncError(RuntimeError):
    """Erro recuperável na leitura ou validação da fonte oficial."""


def normalize_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


class NewsListingParser(HTMLParser):
    """Extrai cartões li.news-item da página oficial renderizada no servidor."""

    FIELDS = {
        ("span", "news-time"): "date",
        ("span", "news-category"): "category",
        ("h4", "news-title"): "title",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.li_depth = 0
        self.capture_field: str | None = None
        self.capture_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "li":
            if self.current is not None:
                self.li_depth += 1
            elif "news-item" in classes:
                self.current = {
                    "id": attr.get("id") or "",
                    "href": "",
                    "date": "",
                    "category": "",
                    "title": "",
                }
                self.li_depth = 1
        if self.current is None:
            return
        if tag == "a" and "news-link" in classes:
            self.current["href"] = attr.get("href") or ""
        for (field_tag, class_name), field in self.FIELDS.items():
            if tag == field_tag and class_name in classes:
                self.capture_field = field
                self.capture_tag = tag
                break

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture_field:
            self.current[self.capture_field] += data

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if tag == self.capture_tag:
            self.capture_field = None
            self.capture_tag = None
        if tag == "li":
            self.li_depth -= 1
            if self.li_depth <= 0:
                self.items.append({key: normalize_text(value) for key, value in self.current.items()})
                self.current = None
                self.li_depth = 0
                self.capture_field = None
                self.capture_tag = None


def validate_listing_item(item: dict[str, str]) -> dict[str, object]:
    article_id = item.get("id", "").strip()
    if not article_id.isdigit():
        raise NewsSyncError("A página oficial trouxe um cartão sem ID numérico.")
    href = item.get("href", "").strip()
    absolute_url = urljoin(SOURCE_URL, href)
    parsed = urlparse(absolute_url)
    match = re.fullmatch(r"/pt/article/(\d+)/?", parsed.path)
    if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST or not match:
        raise NewsSyncError(f"Link de notícia fora do formato oficial esperado: {href!r}")
    if match.group(1) != article_id:
        raise NewsSyncError("O ID do cartão e o ID do link da notícia não correspondem.")
    date_text = item.get("date", "").strip()
    try:
        datetime.strptime(date_text, "%d/%m/%Y")
    except ValueError as exc:
        raise NewsSyncError(f"Data de notícia inválida: {date_text!r}") from exc
    title = item.get("title", "").strip()
    category = item.get("category", "").strip()
    if not title or not category:
        raise NewsSyncError("A página oficial trouxe um cartão sem título ou categoria.")
    return {
        "id": int(article_id),
        "date": date_text,
        "category": category,
        "title": title,
        "summary": FALLBACK_SUMMARY,
        "url": absolute_url,
    }


class ArticleSummaryParser(HTMLParser):
    """Obtém o primeiro parágrafo informativo depois do título do artigo."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.seen_h1 = False
        self.in_first_h1 = False
        self.in_paragraph = False
        self.parts: list[str] = []
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h1" and not self.seen_h1:
            self.in_first_h1 = True
        elif tag == "p" and self.seen_h1 and not self.in_paragraph:
            self.in_paragraph = True
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.in_paragraph:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self.in_first_h1:
            self.in_first_h1 = False
            self.seen_h1 = True
        elif tag == "p" and self.in_paragraph:
            value = normalize_text(" ".join(self.parts))
            if len(value) >= 25:
                self.candidates.append(value)
            self.in_paragraph = False
            self.parts = []


def fetch_html(url: str) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=25) as response:
                if response.status != 200:
                    raise NewsSyncError(f"A fonte oficial respondeu HTTP {response.status}.")
                final_url = response.geturl()
                if urlparse(final_url).hostname != OFFICIAL_HOST:
                    raise NewsSyncError("A fonte oficial redirecionou para um domínio não autorizado.")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise NewsSyncError("A resposta da Garena excedeu o limite de tamanho configurado.")
            return final_url, payload.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise NewsSyncError(f"Não foi possível ler a fonte oficial após três tentativas: {last_error}")


def extract_summary(url: str) -> str:
    final_url, source = fetch_html(url)
    final = urlparse(final_url)
    if final.hostname != OFFICIAL_HOST or not final.path.startswith("/pt/article/"):
        return FALLBACK_SUMMARY
    parser = ArticleSummaryParser()
    parser.feed(source)
    if not parser.candidates:
        return FALLBACK_SUMMARY
    summary = parser.candidates[0]
    if len(summary) <= 220:
        return summary
    cutoff = summary.rfind(" ", 0, 217)
    if cutoff < 120:
        cutoff = 217
    return summary[:cutoff].rstrip(" ,;:") + "…"


def parse_listing(source: str) -> list[dict[str, object]]:
    parser = NewsListingParser()
    parser.feed(source)
    records = [validate_listing_item(item) for item in parser.items]
    if not records:
        raise NewsSyncError("Nenhum cartão de notícia pôde ser validado na página oficial.")
    seen: set[int] = set()
    unique: list[dict[str, object]] = []
    for record in records:
        article_id = int(record["id"])
        if article_id not in seen:
            seen.add(article_id)
            unique.append(record)
        if len(unique) == LATEST_COUNT:
            break
    return unique


def fetch_latest_news() -> list[dict[str, object]]:
    final_url, source = fetch_html(SOURCE_URL)
    if urlparse(final_url).hostname != OFFICIAL_HOST or not urlparse(final_url).path.startswith("/pt/"):
        raise NewsSyncError("A página oficial de notícias redirecionou para uma rota inesperada.")
    records = parse_listing(source)
    for record in records:
        record["summary"] = extract_summary(str(record["url"]))
    return records


def render_news_js(items: list[dict[str, object]]) -> str:
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    source = json.dumps(SOURCE_URL, ensure_ascii=False)
    return f"window.FF_NEWS = {payload};\nwindow.FF_OFFICIAL_NEWS = {source};\n"


def read_version(gradle: str) -> tuple[int, str]:
    code_match = re.search(r"(?m)^\s*versionCode\s+(\d+)\s*$", gradle)
    name_match = re.search(r"(?m)^\s*versionName\s+['\"]([^'\"]+)['\"]\s*$", gradle)
    if not code_match or not name_match:
        raise NewsSyncError("Não foi possível ler versionCode/versionName de app/build.gradle.")
    return int(code_match.group(1)), name_match.group(1)


def next_patch_version(version_name: str) -> str:
    parts = version_name.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise NewsSyncError(f"Formato de versionName não suportado: {version_name!r}")
    numbers = [int(part) for part in parts]
    if len(numbers) == 1:
        numbers.extend([0, 0])
    elif len(numbers) == 2:
        numbers.append(0)
    numbers[-1] += 1
    return ".".join(str(part) for part in numbers)


def bump_gradle_version(gradle: str) -> tuple[str, int, str]:
    code_match = re.search(r"(?m)^(\s*versionCode\s+)(\d+)(\s*)$", gradle)
    name_match = re.search(r"(?m)^(\s*versionName\s+)(['\"])([^'\"]+)(['\"])(\s*)$", gradle)
    if not code_match or not name_match:
        raise NewsSyncError("Não foi possível incrementar a versão no arquivo Gradle.")
    new_code = int(code_match.group(2)) + 1
    new_name = next_patch_version(name_match.group(3))
    result = gradle[:code_match.start()] + code_match.group(1) + str(new_code) + code_match.group(3) + gradle[code_match.end():]
    name_match = re.search(r"(?m)^(\s*versionName\s+)(['\"])([^'\"]+)(['\"])(\s*)$", result)
    assert name_match is not None
    result = result[:name_match.start()] + name_match.group(1) + name_match.group(2) + new_name + name_match.group(4) + name_match.group(5) + result[name_match.end():]
    return result, new_code, new_name


def sync_footer(index_html: str, version_name: str) -> tuple[str, bool]:
    pattern = re.compile(r"(HEADSHOT SENSITIVITY\s*•\s*VERSÃO\s+)([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
    updated, count = pattern.subn(lambda match: match.group(1) + version_name, index_html, count=1)
    if count != 1:
        raise NewsSyncError("Não foi encontrado o rodapé de versão do app para sincronizar.")
    return updated, updated != index_html


def create_release_notes(items: list[dict[str, object]], version_name: str) -> str:
    lines = [
        f"Atualização do Headshot Sensitivity {version_name}.",
        "",
        "A aba de notícias foi sincronizada com publicações oficiais da Garena em português.",
        "",
        "Notícias incluídas:",
    ]
    for item in items:
        title = str(item["title"]).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        lines.append(f"- [{title}]({item['url']}) — {item['date']}.")
    lines.extend([
        "",
        "O APK mantém o mesmo pacote e a mesma assinatura do app anterior. Baixe e confirme a atualização no Android; não é necessário desinstalar a versão instalada.",
    ])
    return "\n".join(lines) + "\n"


def write_github_outputs(values: dict[str, object]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Busca e mostra mudanças sem gravar arquivos.")
    parser.add_argument("--notes-file", type=Path, help="Caminho opcional para salvar notas de release em Markdown.")
    args = parser.parse_args()

    items = fetch_latest_news()
    news_js = render_news_js(items)
    old_news = NEWS_FILE.read_text(encoding="utf-8") if NEWS_FILE.exists() else ""
    gradle = GRADLE_FILE.read_text(encoding="utf-8")
    index_html = INDEX_FILE.read_text(encoding="utf-8")
    current_code, current_name = read_version(gradle)
    footer_synced, footer_changed = sync_footer(index_html, current_name)
    needs_update = news_js != old_news or footer_changed

    if needs_update:
        updated_gradle, version_code, version_name = bump_gradle_version(gradle)
        updated_index, _ = sync_footer(index_html, version_name)
    else:
        updated_gradle, version_code, version_name = gradle, current_code, current_name
        updated_index = index_html

    if args.notes_file:
        args.notes_file.parent.mkdir(parents=True, exist_ok=True)
        args.notes_file.write_text(create_release_notes(items, version_name), encoding="utf-8")

    if args.dry_run:
        print(json.dumps({"changed": needs_update, "versionCode": version_code, "versionName": version_name, "news": items}, ensure_ascii=False, indent=2))
        return 0

    if needs_update:
        NEWS_FILE.write_text(news_js, encoding="utf-8")
        GRADLE_FILE.write_text(updated_gradle, encoding="utf-8")
        INDEX_FILE.write_text(updated_index, encoding="utf-8")

    write_github_outputs({
        "changed": needs_update,
        "version_code": version_code,
        "version_name": version_name,
        "article_count": len(items),
    })
    print(f"{'Atualizada' if needs_update else 'Sem mudanças'} a aba de notícias; versão {version_name} (versionCode {version_code}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NewsSyncError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
