"""Standalone probe for WebpageService fetch/parse behavior."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List

from src.api.services.webpage_service import WebpageService


def _dedupe(urls: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe WebpageService for a list of URLs.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="URLs to fetch (space separated).",
    )
    parser.add_argument(
        "--text",
        help="Text to extract URLs from (uses the same extractor as backend).",
    )
    parser.add_argument(
        "--config",
        help="Optional path to webpage_config.yaml.",
    )
    parser.add_argument(
        "--show-content",
        action="store_true",
        help="Print full extracted content.",
    )
    parser.add_argument(
        "--snippet-len",
        type=int,
        default=200,
        help="Snippet length when not using --show-content.",
    )
    return parser.parse_args()


async def _probe_url(service: WebpageService, url: str, args: argparse.Namespace) -> None:
    try:
        result = await service.fetch_and_parse(url)
    except Exception as exc:
        print("-----")
        print(f"URL: {url}")
        print(f"Unhandled error: {exc}")
        return

    print("-----")
    print(f"URL: {url}")
    print(f"Final URL: {result.final_url}")
    print(f"Status: {result.status_code}")
    print(f"Content-Type: {result.content_type}")
    print(f"Title: {result.title}")
    print(f"Text chars: {len(result.text or '')}")
    print(f"Truncated: {result.truncated}")
    print(f"Error: {result.error or 'None'}")

    if result.text:
        if args.show_content:
            print("Content:")
            print(result.text)
        else:
            snippet = " ".join(result.text.split())
            if len(snippet) > args.snippet_len:
                snippet = snippet[: args.snippet_len] + "..."
            print(f"Snippet: {snippet}")


async def main() -> int:
    args = _parse_args()
    service = WebpageService(config_path=args.config) if args.config else WebpageService()

    urls: List[str] = []
    if args.text:
        urls.extend(service.extract_urls(args.text))
    urls.extend(args.urls)
    urls = _dedupe([u for u in urls if u])

    if not urls:
        print("No URLs provided. Use positional URLs or --text.")
        return 2

    print("Webpage config:")
    print(f"  enabled: {service.config.enabled}")
    print(f"  max_urls: {service.config.max_urls}")
    print(f"  timeout_seconds: {service.config.timeout_seconds}")
    print(f"  max_bytes: {service.config.max_bytes}")
    print(f"  max_content_chars: {service.config.max_content_chars}")
    print(f"  user_agent: {service.config.user_agent}")
    print(f"  proxy: {service.config.proxy}")
    print(f"  trust_env: {service.config.trust_env}")
    print(f"  diagnostics_enabled: {service.config.diagnostics_enabled}")
    print(f"  diagnostics_timeout_seconds: {service.config.diagnostics_timeout_seconds}")

    for url in urls:
        await _probe_url(service, url, args)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
