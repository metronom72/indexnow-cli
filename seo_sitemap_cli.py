#!/usr/bin/env python3
"""
SEO Sitemap CLI Tool
Tool for working with sitemap.xml, IndexNow submission and SEO analysis
"""

import csv
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import click
import requests


@dataclass
class URLAnalysis:
    url: str
    status_code: int
    response_time: float
    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1_tags: List[str] = None
    canonical_url: Optional[str] = None
    robots_meta: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    has_schema_markup: bool = False
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.h1_tags is None:
            self.h1_tags = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class SitemapParser:
    """Parser for sitemap.xml files"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SEO-Sitemap-Tool/1.0"})

    def parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse sitemap.xml and return list of URLs"""
        try:
            click.echo(f"[REQUEST] Fetching sitemap: {sitemap_url}")

            # Handle local file URLs
            if sitemap_url.startswith("file://"):
                file_path = sitemap_url.replace("file://", "")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                click.echo(f"[FILE] Loaded local file: {file_path}")
            else:
                click.echo(f"[CURL] curl -H 'User-Agent: SEO-Sitemap-Tool/1.0' '{sitemap_url}'")
                response = self.session.get(sitemap_url, timeout=self.timeout)
                response.raise_for_status()
                content = response.content
                click.echo(f"[RESPONSE] Status: {response.status_code}, Size: {len(content)} bytes")

            root = ET.fromstring(content)
            urls = []

            # Handle regular sitemap
            for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if url_elem.text:
                    urls.append(url_elem.text.strip())

            # Handle sitemap index
            sitemap_urls = []
            for sitemap_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"):
                loc_elem = sitemap_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if loc_elem is not None and loc_elem.text:
                    sitemap_urls.append(loc_elem.text.strip())

            if sitemap_urls:
                click.echo(f"[SITEMAP INDEX] Found {len(sitemap_urls)} nested sitemaps")
                for idx, nested_url in enumerate(sitemap_urls, 1):
                    click.echo(f"[NESTED {idx}] {nested_url}")

            # Recursively process nested sitemaps
            for sitemap_url in sitemap_urls:
                try:
                    nested_urls = self.parse_sitemap(sitemap_url)
                    urls.extend(nested_urls)
                except Exception as e:
                    click.echo(f"Error processing nested sitemap {sitemap_url}: {e}", err=True)

            # Check for duplicates
            unique_urls = list(set(urls))
            duplicates_count = len(urls) - len(unique_urls)

            click.echo(f"[PARSED] Found {len(urls)} total URLs, {len(unique_urls)} unique")

            if duplicates_count > 0:
                click.echo(f"[DUPLICATES] Found {duplicates_count} duplicate URLs")
                # Find and display duplicates
                from collections import Counter

                url_counts = Counter(urls)
                duplicates = [url for url, count in url_counts.items() if count > 1]

                click.echo("[DUPLICATE LIST]")
                for duplicate_url in duplicates:
                    count = url_counts[duplicate_url]
                    click.echo(f"  {count}x: {duplicate_url}")

            return unique_urls

        except (requests.RequestException, FileNotFoundError, IOError) as e:
            raise click.ClickException(f"Error loading sitemap: {e}")
        except ET.ParseError as e:
            raise click.ClickException(f"Error parsing XML: {e}")


class IndexNowSubmitter:
    """Class for submitting URLs to IndexNow"""

    # Static endpoints for major search engines
    STATIC_ENDPOINTS = {"bing": "https://api.indexnow.org/indexnow", "yandex": "https://yandex.com/indexnow"}

    def __init__(self, api_key: str, key_location: str, timeout: int = 30):
        self.api_key = api_key
        self.key_location = key_location
        self.timeout = timeout
        self.session = requests.Session()
        self.available_engines = {}
        self._load_search_engines()

    def _load_search_engines(self):
        """Load available search engines from IndexNow registry"""
        try:
            click.echo("[REGISTRY] Loading search engines from https://www.indexnow.org/searchengines.json")
            response = self.session.get("https://www.indexnow.org/searchengines.json", timeout=self.timeout)
            response.raise_for_status()

            engines_registry = response.json()
            click.echo(f"[REGISTRY] Found {len(engines_registry)} registered search engines")

            # Load metadata for each engine
            for engine_id, meta_url in engines_registry.items():
                try:
                    meta_response = self.session.get(meta_url, timeout=self.timeout)
                    if meta_response.status_code == 200:
                        meta_data = meta_response.json()
                        if "api" in meta_data and not meta_data.get("unsubscribe", False):
                            self.available_engines[engine_id] = {
                                "name": meta_data.get("name", engine_id),
                                "api": meta_data["api"],
                                "host": meta_data.get("host", ""),
                                "homepage": meta_data.get("homepage", ""),
                            }
                            click.echo(f"[ENGINE] Loaded: {engine_id} - {meta_data.get('name', 'Unknown')}")
                        else:
                            click.echo(f"[ENGINE] Skipped: {engine_id} (unsubscribed or no API)")
                    else:
                        click.echo(
                            f"[ENGINE] Failed to load metadata for {engine_id}: HTTP {meta_response.status_code}"
                        )
                except Exception as e:
                    click.echo(f"[ENGINE] Error loading {engine_id}: {e}")

        except Exception as e:
            click.echo(f"[REGISTRY] Failed to load search engines registry: {e}")
            click.echo("[REGISTRY] Falling back to static endpoints")

    def get_available_engines(self):
        """Get list of available search engines"""
        engines = {}
        # Add static endpoints
        engines.update(self.STATIC_ENDPOINTS)
        # Add dynamic endpoints
        for engine_id, data in self.available_engines.items():
            engines[engine_id] = data["api"]
        return engines

    def submit_urls(self, urls: List[str], host: str, endpoint: str = "bing") -> Dict:
        """Submit URLs to IndexNow"""
        # Determine endpoint URL
        endpoint_url = None
        engine_name = endpoint

        # Check static endpoints first
        if endpoint in self.STATIC_ENDPOINTS:
            endpoint_url = self.STATIC_ENDPOINTS[endpoint]
        # Check dynamic endpoints
        elif endpoint in self.available_engines:
            endpoint_url = self.available_engines[endpoint]["api"]
            engine_name = self.available_engines[endpoint]["name"]
        else:
            # Try to use endpoint as direct URL
            if endpoint.startswith("http"):
                endpoint_url = endpoint
            else:
                available = list(self.get_available_engines().keys())
                raise ValueError(f"Unsupported endpoint: {endpoint}. Available: {', '.join(available)}")

        payload = {"host": host, "key": self.api_key, "keyLocation": self.key_location, "urlList": urls}

        # Log the curl command equivalent
        import json as json_lib

        click.echo(f"[INDEXNOW] Submitting to {engine_name} ({endpoint})")
        click.echo(f"[ENDPOINT] {endpoint_url}")
        click.echo(f"[CURL] curl -X POST '{endpoint_url}' \\")
        click.echo("  -H 'Content-Type: application/json; charset=utf-8' \\")
        click.echo(f"  -d '{json_lib.dumps(payload)}'")

        try:
            response = self.session.post(
                endpoint_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

            click.echo(f"[RESPONSE] Status: {response.status_code}")
            click.echo(f"[RESPONSE] Body: {response.text if response.text else 'Empty'}")

            # Handle different response codes according to IndexNow spec
            success_codes = [200, 202]
            if response.status_code == 200:
                click.echo("[STATUS] URL submitted successfully")
            elif response.status_code == 202:
                click.echo("[STATUS] URL received. IndexNow key validation pending")
            elif response.status_code == 400:
                click.echo("[ERROR] Bad request - Invalid format")
            elif response.status_code == 403:
                click.echo("[ERROR] Forbidden - Key not valid (key not found or file found but key not in file)")
            elif response.status_code == 422:
                click.echo("[ERROR] Unprocessable Entity - URLs don't belong to host or key doesn't match schema")
            elif response.status_code == 429:
                click.echo("[ERROR] Too Many Requests - Potential spam detected")

            return {
                "status_code": response.status_code,
                "success": response.status_code in success_codes,
                "response": response.text if response.text else "No response body",
                "endpoint": endpoint,
                "endpoint_url": endpoint_url,
            }

        except requests.RequestException as e:
            click.echo(f"[ERROR] Request failed: {e}")
            return {
                "status_code": 0,
                "success": False,
                "response": str(e),
                "endpoint": endpoint,
                "endpoint_url": endpoint_url,
            }


class SEOAnalyzer:
    """SEO analyzer for URLs"""

    def __init__(self, timeout: int = 30, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    def analyze_url(self, url: str) -> URLAnalysis:
        """Analyze single URL"""
        start_time = time.time()

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response_time = time.time() - start_time

            analysis = URLAnalysis(url=url, status_code=response.status_code, response_time=response_time)

            if response.status_code == 200:
                self._analyze_content(response.text, analysis)
            else:
                analysis.errors.append(f"HTTP {response.status_code}")

            return analysis

        except requests.RequestException as e:
            response_time = time.time() - start_time
            return URLAnalysis(url=url, status_code=0, response_time=response_time, errors=[f"Request error: {str(e)}"])

    def _analyze_content(self, html: str, analysis: URLAnalysis):
        """Analyze HTML content"""
        # Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            analysis.title = title_match.group(1).strip()
            if len(analysis.title) > 60:
                analysis.warnings.append("Title too long (>60 characters)")
            elif len(analysis.title) < 30:
                analysis.warnings.append("Title too short (<30 characters)")
        else:
            analysis.errors.append("Missing title")

        # Meta description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE
        )
        if desc_match:
            analysis.meta_description = desc_match.group(1).strip()
            if len(analysis.meta_description) > 160:
                analysis.warnings.append("Meta description too long (>160 characters)")
            elif len(analysis.meta_description) < 120:
                analysis.warnings.append("Meta description too short (<120 characters)")
        else:
            analysis.errors.append("Missing meta description")

        # H1 tags
        h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        analysis.h1_tags = [re.sub(r"<[^>]+>", "", h1).strip() for h1 in h1_matches]

        if len(analysis.h1_tags) == 0:
            analysis.errors.append("Missing H1")
        elif len(analysis.h1_tags) > 1:
            analysis.warnings.append("Multiple H1 tags")

        # Canonical URL
        canonical_match = re.search(
            r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']*)["\']', html, re.IGNORECASE
        )
        if canonical_match:
            analysis.canonical_url = canonical_match.group(1).strip()

        # Robots meta
        robots_match = re.search(
            r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE
        )
        if robots_match:
            analysis.robots_meta = robots_match.group(1).strip()

        # Open Graph
        og_title_match = re.search(
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE
        )
        if og_title_match:
            analysis.og_title = og_title_match.group(1).strip()

        og_desc_match = re.search(
            r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE
        )
        if og_desc_match:
            analysis.og_description = og_desc_match.group(1).strip()

        # Schema markup
        analysis.has_schema_markup = bool(re.search(r"application/ld\+json|microdata|@type", html, re.IGNORECASE))

        # Additional checks
        if not analysis.og_title:
            analysis.warnings.append("Missing og:title")
        if not analysis.og_description:
            analysis.warnings.append("Missing og:description")
        if not analysis.has_schema_markup:
            analysis.warnings.append("Missing structured markup")

    def analyze_urls_batch(self, urls: List[str]) -> List[URLAnalysis]:
        """Analyze list of URLs in multi-threaded mode"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.analyze_url, url): url for url in urls}

            with click.progressbar(length=len(urls), label="Analyzing URLs") as bar:
                for future in as_completed(future_to_url):
                    result = future.result()
                    results.append(result)
                    bar.update(1)

        return results


class ReportGenerator:
    """Report generator"""

    @staticmethod
    def generate_csv_report(analyses: List[URLAnalysis], filename: str):
        """Generate CSV report"""
        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "URL",
                "Status Code",
                "Response Time (s)",
                "Title",
                "Title Length",
                "Meta Description",
                "Meta Description Length",
                "H1 Count",
                "H1 Tags",
                "Canonical URL",
                "Robots Meta",
                "OG Title",
                "OG Description",
                "Has Schema Markup",
                "Errors",
                "Warnings",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for analysis in analyses:
                writer.writerow(
                    {
                        "URL": analysis.url,
                        "Status Code": analysis.status_code,
                        "Response Time (s)": round(analysis.response_time, 2),
                        "Title": analysis.title or "",
                        "Title Length": len(analysis.title) if analysis.title else 0,
                        "Meta Description": analysis.meta_description or "",
                        "Meta Description Length": len(analysis.meta_description) if analysis.meta_description else 0,
                        "H1 Count": len(analysis.h1_tags),
                        "H1 Tags": "; ".join(analysis.h1_tags),
                        "Canonical URL": analysis.canonical_url or "",
                        "Robots Meta": analysis.robots_meta or "",
                        "OG Title": analysis.og_title or "",
                        "OG Description": analysis.og_description or "",
                        "Has Schema Markup": analysis.has_schema_markup,
                        "Errors": "; ".join(analysis.errors),
                        "Warnings": "; ".join(analysis.warnings),
                    }
                )

    @staticmethod
    def generate_summary_report(analyses: List[URLAnalysis]) -> Dict:
        """Generate summary report"""
        total_urls = len(analyses)
        successful_urls = len([a for a in analyses if a.status_code == 200])
        error_urls = len([a for a in analyses if a.status_code != 200])

        avg_response_time = sum(a.response_time for a in analyses) / total_urls if total_urls > 0 else 0

        # Count errors and warnings
        total_errors = sum(len(a.errors) for a in analyses)
        total_warnings = sum(len(a.warnings) for a in analyses)

        # Most frequent issues
        all_errors = []
        all_warnings = []
        for analysis in analyses:
            all_errors.extend(analysis.errors)
            all_warnings.extend(analysis.warnings)

        from collections import Counter

        common_errors = Counter(all_errors).most_common(5)
        common_warnings = Counter(all_warnings).most_common(5)

        return {
            "total_urls": total_urls,
            "successful_urls": successful_urls,
            "error_urls": error_urls,
            "success_rate": (successful_urls / total_urls * 100) if total_urls > 0 else 0,
            "avg_response_time": round(avg_response_time, 2),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "common_errors": common_errors,
            "common_warnings": common_warnings,
        }


# CLI Commands
@click.group()
@click.version_option(version="1.0.0")
def cli():
    """SEO Sitemap CLI Tool - tool for working with sitemap.xml and IndexNow"""
    pass


@cli.command()
@click.argument("sitemap_url")
@click.option("--api-key", required=True, help="IndexNow API key")
@click.option("--key-location", required=True, help="URL where API key file is hosted")
@click.option("--host", help="Site host (if different from sitemap URL)")
@click.option("--endpoint", default="bing", help="IndexNow endpoint (engine ID, name, or URL)")
@click.option("--batch-size", default=100, help="URL batch size for submission")
@click.option("--delay", default=1, help="Delay between requests (seconds)")
@click.option("--verbose", "-v", is_flag=True, help="Show all URLs being submitted")
@click.option("--list-engines", is_flag=True, help="List all available search engines and exit")
def submit(sitemap_url, api_key, key_location, host, endpoint, batch_size, delay, verbose, list_engines):
    """Submit URLs from sitemap to IndexNow"""

    # Create submitter to load engines
    submitter = IndexNowSubmitter(api_key, key_location)

    # List engines and exit if requested
    if list_engines:
        click.echo("\nAvailable IndexNow Search Engines:")
        click.echo("=" * 60)

        # Show static engines
        if submitter.STATIC_ENDPOINTS:
            click.echo("\nStatic Endpoints:")
            click.echo("-" * 30)
            for engine_id, url in submitter.STATIC_ENDPOINTS.items():
                click.echo(f"  {engine_id:15} -> {url}")

        # Show dynamic engines
        if submitter.available_engines:
            click.echo("\nDynamic Endpoints (from registry):")
            click.echo("-" * 40)
            for engine_id, data in submitter.available_engines.items():
                name = data["name"]
                api = data["api"]
                homepage = data.get("homepage", "")
                click.echo(f"  {engine_id:15} {name}")
                click.echo(f"  {' ' * 15} API: {api}")
                if homepage:
                    click.echo(f"  {' ' * 15} Web: {homepage}")
                click.echo()

        click.echo("Usage examples:")
        click.echo("  --endpoint bing")
        click.echo("  --endpoint yandex")
        click.echo("  --endpoint <any_engine_id_from_above>")
        click.echo("  --endpoint https://custom-search-engine.com/indexnow")
        return

    click.echo(f"Parsing sitemap: {sitemap_url}")

    # Parse sitemap
    parser = SitemapParser()
    urls = parser.parse_sitemap(sitemap_url)

    click.echo(f"Found {len(urls)} URLs")

    if not urls:
        click.echo("No URLs found in sitemap", err=True)
        return

    # Show URLs if verbose mode
    if verbose:
        click.echo("\n" + "=" * 50)
        click.echo("URLS TO SUBMIT:")
        click.echo("=" * 50)
        for idx, url in enumerate(urls, 1):
            click.echo(f"{idx:3d}. {url}")
        click.echo("=" * 50 + "\n")

    # Determine host if not specified
    if not host:
        parsed_url = urlparse(sitemap_url)
        host = parsed_url.netloc

    click.echo(f"Target host: {host}")
    click.echo(f"API key: {api_key}")
    click.echo(f"Key location: {key_location}")

    # Submit URLs in batches
    total_submitted = 0
    successful_batches = 0

    for i in range(0, len(urls), batch_size):
        batch = urls[i : i + batch_size]

        click.echo(
            f"\nSubmitting batch {i // batch_size + 1}/{(len(urls) + batch_size - 1) // batch_size} ({len(batch)} URLs)"
        )

        if verbose:
            click.echo("Batch URLs:")
            for url in batch:
                click.echo(f"  - {url}")

        result = submitter.submit_urls(batch, host, endpoint)

        if result["success"]:
            successful_batches += 1
            total_submitted += len(batch)
            click.echo(f"Successfully submitted {len(batch)} URLs")
        else:
            click.echo(f"Submission error: {result['response']}", err=True)

        if delay > 0 and i + batch_size < len(urls):
            click.echo(f"Waiting {delay} seconds before next batch...")
            time.sleep(delay)

    click.echo(f"\nTotal submitted: {total_submitted}/{len(urls)} URLs")
    click.echo(f"Successful batches: {successful_batches}/{(len(urls) + batch_size - 1) // batch_size}")


@cli.command()
@click.argument("sitemap_url")
@click.option("--output", default="seo_report", help="Report file prefix")
@click.option("--max-workers", default=10, help="Number of threads for analysis")
@click.option("--timeout", default=30, help="HTTP request timeout")
def analyze(sitemap_url, output, max_workers, timeout):
    """Analyze SEO for all URLs from sitemap"""

    click.echo(f"Parsing sitemap: {sitemap_url}")

    # Parse sitemap
    parser = SitemapParser(timeout=timeout)
    urls = parser.parse_sitemap(sitemap_url)

    click.echo(f"Found {len(urls)} URLs for analysis")

    if not urls:
        click.echo("No URLs found in sitemap", err=True)
        return

    # Analyze URLs
    analyzer = SEOAnalyzer(timeout=timeout, max_workers=max_workers)
    analyses = analyzer.analyze_urls_batch(urls)

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{output}_{timestamp}.csv"

    click.echo(f"\nSaving detailed report to: {csv_filename}")
    ReportGenerator.generate_csv_report(analyses, csv_filename)

    # Show summary report
    summary = ReportGenerator.generate_summary_report(analyses)

    click.echo("\n" + "=" * 60)
    click.echo("SUMMARY REPORT")
    click.echo("=" * 60)
    click.echo(f"Total URLs: {summary['total_urls']}")
    click.echo(f"Successfully analyzed: {summary['successful_urls']}")
    click.echo(f"Accessibility errors: {summary['error_urls']}")
    click.echo(f"Success rate: {summary['success_rate']:.1f}%")
    click.echo(f"Average response time: {summary['avg_response_time']} sec")
    click.echo(f"Total SEO errors: {summary['total_errors']}")
    click.echo(f"Total warnings: {summary['total_warnings']}")

    if summary["common_errors"]:
        click.echo("\nMost frequent errors:")
        for error, count in summary["common_errors"]:
            click.echo(f"  • {error}: {count} times")

    if summary["common_warnings"]:
        click.echo("\nMost frequent warnings:")
        for warning, count in summary["common_warnings"]:
            click.echo(f"  • {warning}: {count} times")


@cli.command()
@click.argument("sitemap_url")
@click.option("--timeout", default=10, help="Accessibility check timeout")
@click.option("--max-workers", default=20, help="Number of threads")
def check_availability(sitemap_url, timeout, max_workers):
    """Quick availability check for all URLs from sitemap"""

    click.echo(f"Parsing sitemap: {sitemap_url}")

    # Parse sitemap
    parser = SitemapParser(timeout=timeout)
    urls = parser.parse_sitemap(sitemap_url)

    click.echo(f"Checking availability of {len(urls)} URLs")

    if not urls:
        click.echo("No URLs found in sitemap", err=True)
        return

    def check_url(url):
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return url, response.status_code, True
        except requests.RequestException:
            return url, 0, False

    available = 0
    unavailable = 0
    unavailable_urls = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_url, url): url for url in urls}

        with click.progressbar(length=len(urls), label="Checking availability") as bar:
            for future in as_completed(futures):
                url, status_code, is_available = future.result()

                if is_available and status_code == 200:
                    available += 1
                else:
                    unavailable += 1
                    unavailable_urls.append((url, status_code))

                bar.update(1)

    click.echo(f"\nAvailable: {available}")
    click.echo(f"Unavailable: {unavailable}")
    click.echo(f"Availability rate: {(available / len(urls) * 100):.1f}%")

    if unavailable_urls:
        click.echo("\nUnavailable URLs:")
        for url, status_code in unavailable_urls[:10]:  # Show first 10
            click.echo(f"  {status_code}: {url}")

        if len(unavailable_urls) > 10:
            click.echo(f"  ... and {len(unavailable_urls) - 10} more URLs")


if __name__ == "__main__":
    cli()
