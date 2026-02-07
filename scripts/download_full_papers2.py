#!/usr/bin/env python3
"""
download_papers.py - Download arXiv papers with HTML-first fallback

Downloads papers from scored_papers.json using a two-tier strategy:
1. Try HTML first (available for papers submitted after Dec 2023)
   → Convert to clean TXT, delete HTML
2. Fall back to PDF + text extraction if HTML unavailable
   → Extract text to TXT, delete PDF

Output directory: resources/papers/
- {arxiv_id}.txt (clean text from HTML or PDF)
- download_metadata.json (tracking what was downloaded)
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# Try to import PDF libraries (PyMuPDF preferred, fallback to PyPDF2)
try:
    import fitz  # PyMuPDF
    PDF_LIBRARY = "pymupdf"
except ImportError:
    try:
        import PyPDF2
        PDF_LIBRARY = "pypdf2"
    except ImportError:
        PDF_LIBRARY = None
        print("⚠️  Warning: No PDF library found. Install with:")
        print("   pip install PyMuPDF --break-system-packages")
        print("   or: pip install PyPDF2 --break-system-packages")


# Configuration
workspace = Path.home() / ".openclaw/workspaces/research-assistant"
SCORED_PAPERS_PATH = workspace / "resources" / "scored_papers_summary.json"
OUTPUT_DIR = workspace / "resources/papers"
DOWNLOAD_METADATA_PATH = OUTPUT_DIR / "download_metadata.json"

# Rate limiting (arXiv requests 3 seconds between requests)
REQUEST_DELAY = 3.0

# User agent (arXiv requires identification)
HEADERS = {
    "User-Agent": "arXiv-Curator-Bot/1.0 (Academic Research; mailto:researcher@example.com)"
}


class PaperDownloader:
    """Handles downloading papers from arXiv with HTML-first fallback."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "total": 0,
            "html_success": 0,
            "pdf_fallback": 0,
            "failed": 0,
            "skipped": 0
        }
        self.download_metadata = []
        
    def _extract_text_from_html(self, html_path: Path, txt_path: Path) -> Tuple[bool, int]:
        """Extract clean text from HTML file."""
        try:
            # Read HTML content
            html_content = html_path.read_text(encoding='utf-8')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Get text content
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up multiple newlines
            lines = [line.strip() for line in text.split('\n')]
            lines = [line for line in lines if line]  # Remove empty lines
            text = '\n\n'.join(lines)
            
            # Save extracted text
            txt_path.write_text(text, encoding='utf-8')
            
            # Delete HTML after successful extraction
            html_path.unlink()
            
            size_kb = len(text) / 1024
            print(f"    ✓ Text extracted from HTML ({size_kb:.1f} KB, {len(text.split())} words)")
            print(f"    ✓ HTML deleted (keeping .txt only)")
            
            return True, len(text)
            
        except Exception as e:
            print(f"    ⚠️  Text extraction from HTML failed: {e}")
            return False, 0
    
    def download_paper(self, paper: Dict) -> Dict:
        """
        Download a single paper using HTML-first fallback strategy.
        
        Returns metadata dict with download results.
        """
        arxiv_id = paper["arxiv_id"]
        self.stats["total"] += 1
        
        print(f"\n[{self.stats['total']}] Processing: {arxiv_id}")
        print(f"    Title: {paper['title'][:70]}...")
        
        # Check if already downloaded
        html_path = self.output_dir / f"{arxiv_id}.html"
        pdf_path = self.output_dir / f"{arxiv_id}.pdf"
        txt_path = self.output_dir / f"{arxiv_id}.txt"
        
        if txt_path.exists():
            print(f"    ✓ Already downloaded, skipping")
            self.stats["skipped"] += 1
            return self._create_metadata(paper, "skipped", None, None)
        
        # Strategy 1: Try HTML first
        html_success, html_size = self._try_download_html(arxiv_id, html_path)
        
        if html_success:
            # Extract text from HTML
            txt_success, txt_size = self._extract_text_from_html(html_path, txt_path)
            
            if txt_success:
                self.stats["html_success"] += 1
                return self._create_metadata(
                    paper, 
                    "html", 
                    html_size, 
                    txt_path,
                    txt_extracted=True,
                    txt_size=txt_size
                )
            else:
                # HTML download succeeded but text extraction failed
                # Keep the HTML file and mark as partial success
                self.stats["html_success"] += 1
                return self._create_metadata(paper, "html", html_size, html_path)
        
        # Strategy 2: Fall back to PDF
        print(f"    → HTML not available, falling back to PDF")
        pdf_success, pdf_size = self._try_download_pdf(arxiv_id, pdf_path)
        
        if not pdf_success:
            self.stats["failed"] += 1
            return self._create_metadata(paper, "failed", None, None)
        
        # Extract text from PDF
        txt_success, txt_size = self._extract_text_from_pdf(pdf_path, txt_path)
        
        self.stats["pdf_fallback"] += 1
        return self._create_metadata(
            paper, 
            "pdf", 
            pdf_size, 
            pdf_path,
            txt_extracted=txt_success,
            txt_size=txt_size
        )
    
    def _try_download_html(self, arxiv_id: str, output_path: Path) -> Tuple[bool, int]:
        """Try to download HTML version of paper."""
        url = f"https://arxiv.org/html/{arxiv_id}"
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            
            if response.status_code == 404:
                print(f"    ✗ HTML not available (404)")
                return False, 0
            
            response.raise_for_status()
            
            # Parse HTML and extract main content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove navigation, scripts, and other non-content elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Save cleaned HTML
            html_content = soup.prettify()
            output_path.write_text(html_content, encoding='utf-8')
            
            size_kb = len(html_content) / 1024
            print(f"    ✓ HTML downloaded ({size_kb:.1f} KB)")
            
            return True, len(html_content)
            
        except requests.RequestException as e:
            print(f"    ✗ HTML download failed: {e}")
            return False, 0
    
    def _try_download_pdf(self, arxiv_id: str, output_path: Path) -> Tuple[bool, int]:
        """Download PDF version of paper."""
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=60, stream=True)
            response.raise_for_status()
            
            # Download PDF in chunks
            with output_path.open('wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            size_kb = output_path.stat().st_size / 1024
            print(f"    ✓ PDF downloaded ({size_kb:.1f} KB)")
            
            return True, output_path.stat().st_size
            
        except requests.RequestException as e:
            print(f"    ✗ PDF download failed: {e}")
            return False, 0
    
    def _extract_text_from_pdf(self, pdf_path: Path, txt_path: Path) -> Tuple[bool, int]:
        """Extract text from PDF file."""
        if PDF_LIBRARY is None:
            print(f"    ⚠️  No PDF library available, skipping text extraction")
            return False, 0
        
        try:
            if PDF_LIBRARY == "pymupdf":
                # PyMuPDF (fitz) - recommended
                doc = fitz.open(pdf_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                
            elif PDF_LIBRARY == "pypdf2":
                # PyPDF2 - fallback
                with pdf_path.open('rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
            
            # Save extracted text
            txt_path.write_text(text, encoding='utf-8')
            
            size_kb = len(text) / 1024
            print(f"    ✓ Text extracted ({size_kb:.1f} KB, {len(text.split())} words)")
            
            return True, len(text)
            
        except Exception as e:
            print(f"    ⚠️  Text extraction failed: {e}")
            return False, 0
    
    def _create_metadata(
        self, 
        paper: Dict, 
        status: str, 
        size: int, 
        path: Path,
        txt_extracted: bool = False,
        txt_size: int = 0
    ) -> Dict:
        """Create metadata entry for download."""
        metadata = {
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "score": paper["score"],
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if status == "html":
            metadata["format"] = "html"
            metadata["size_bytes"] = size
            if path:
                metadata["path"] = str(path.relative_to(self.output_dir.parent))
            metadata["text_extracted"] = txt_extracted
            if txt_extracted:
                metadata["text_size_bytes"] = txt_size
        elif status == "pdf":
            metadata["format"] = "pdf"
            metadata["size_bytes"] = size
            metadata["path"] = str(path.relative_to(self.output_dir.parent))
            metadata["text_extracted"] = txt_extracted
            if txt_extracted:
                metadata["text_size_bytes"] = txt_size
        
        return metadata
    
    def save_metadata(self):
        """Save download metadata to JSON file."""
        metadata_output = {
            "download_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": self.stats,
            "papers": self.download_metadata
        }
        
        DOWNLOAD_METADATA_PATH.write_text(
            json.dumps(metadata_output, indent=2),
            encoding='utf-8'
        )
        
        print(f"\n✓ Metadata saved to: {DOWNLOAD_METADATA_PATH}")
    
    def print_summary(self):
        """Print download summary statistics."""
        print("\n" + "=" * 60)
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total papers:      {self.stats['total']}")
        print(f"HTML→TXT:          {self.stats['html_success']} "
              f"({self.stats['html_success']/max(self.stats['total'],1)*100:.1f}%)")
        print(f"PDF→TXT:           {self.stats['pdf_fallback']} "
              f"({self.stats['pdf_fallback']/max(self.stats['total'],1)*100:.1f}%)")
        print(f"Skipped (exists):  {self.stats['skipped']}")
        print(f"Failed:            {self.stats['failed']}")
        print("=" * 60)
        print(f"\nAll papers saved as .txt files in: {self.output_dir}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("arXiv Paper Downloader")
    print("=" * 60)
    
    # Check if scored_papers.json exists
    if not SCORED_PAPERS_PATH.exists():
        print(f"✗ Error: {SCORED_PAPERS_PATH} not found")
        print(f"  Expected path: {SCORED_PAPERS_PATH.absolute()}")
        sys.exit(1)
    
    # Load scored papers
    print(f"\n✓ Loading papers from: {SCORED_PAPERS_PATH}")
    with SCORED_PAPERS_PATH.open() as f:
        data = json.load(f)
    
    papers = data.get("scored_papers_summary", [])
    print(f"✓ Found {len(papers)} papers to download")
    
    if not papers:
        print("✗ No papers to download")
        sys.exit(0)
    
    # Check PDF library
    if PDF_LIBRARY:
        print(f"✓ PDF library: {PDF_LIBRARY}")
    else:
        print("⚠️  No PDF text extraction available")
    
    # Create downloader
    downloader = PaperDownloader(OUTPUT_DIR)
    print(f"✓ Output directory: {OUTPUT_DIR.absolute()}\n")
    
    # Download papers
    for i, paper in enumerate(papers):
        # Rate limiting (skip delay for first request)
        if i > 0:
            print(f"\n⏳ Waiting {REQUEST_DELAY}s (rate limit)...")
            time.sleep(REQUEST_DELAY)
        
        metadata = downloader.download_paper(paper)
        downloader.download_metadata.append(metadata)
    
    # Save metadata and print summary
    downloader.save_metadata()
    downloader.print_summary()
    
    print(f"\n✓ All downloads complete!")
    print(f"  Papers saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
