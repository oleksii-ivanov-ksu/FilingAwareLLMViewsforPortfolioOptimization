#!/usr/bin/env python3
"""
Extract qualitative facts from SEC filings using LLM.

Usage:
    python scripts/extract_facts.py --test           # Test on 10 files
    python scripts/extract_facts.py --ticker AMZN    # Single ticker
    python scripts/extract_facts.py --resume         # Full run with resume
    python scripts/extract_facts.py --dry-run        # Show what would be processed

Output:
    data/extracted/{TICKER}/{FILING_TYPE}_{DATE}.json
"""

import os
import sys
import argparse
import logging
import json
import yaml
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.extraction import FilingExtractor, TokenChunker
from src.extraction.chunker import estimate_cost

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration."""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    with open('config/universe.yaml', 'r') as f:
        universe = yaml.safe_load(f)

    return config, universe


def get_all_tickers(universe: dict) -> list:
    """Get all tickers from universe config."""
    u = universe['universe']
    if 'tickers' in u:
        return u['tickers']
    return u.get('core', []) + u.get('holdout', [])


def count_filings(raw_data_dir: Path, tickers: list) -> dict:
    """Count filings per ticker."""
    counts = {}
    for ticker in tickers:
        filings_dir = raw_data_dir / ticker / "filings"
        if filings_dir.exists():
            counts[ticker] = len(list(filings_dir.glob("*.html")))
        else:
            counts[ticker] = 0
    return counts


def count_extracted(output_dir: Path, tickers: list) -> dict:
    """Count already extracted files per ticker."""
    counts = {}
    for ticker in tickers:
        ticker_dir = output_dir / ticker
        if ticker_dir.exists():
            counts[ticker] = len(list(ticker_dir.glob("*.json")))
        else:
            counts[ticker] = 0
    return counts


def select_test_files(raw_data_dir: Path, tickers: list, n: int = 10) -> list:
    """Select diverse test files across years and tickers."""
    test_files = []

    # Sample from different years
    years_to_sample = [2006, 2010, 2015, 2020, 2024]

    for ticker in tickers[:5]:  # Use first 5 tickers
        filings_dir = raw_data_dir / ticker / "filings"
        if not filings_dir.exists():
            continue

        for year in years_to_sample:
            # Find a 10-K from this year
            pattern = f"10-K_{year}-*.html"
            files = list(filings_dir.glob(pattern))
            if files:
                test_files.append((ticker, files[0]))
                if len(test_files) >= n:
                    return test_files

    return test_files


def main():
    parser = argparse.ArgumentParser(
        description="Extract qualitative facts from SEC filings"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode: process only 10 files"
    )
    parser.add_argument(
        "--ticker", type=str,
        help="Process single ticker"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip already extracted files"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be processed without calling API"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit number of files to process (0 = no limit)"
    )
    parser.add_argument(
        "--workers", type=int, default=5,
        help="Number of parallel workers (default: 5)"
    )

    args = parser.parse_args()

    # Load config
    config, universe = load_config()

    # Get OpenAI/OpenRouter settings from config
    openai_config = config.get('openai', {})
    api_key = openai_config.get('api_key') or os.environ.get('OPENAI_API_KEY')
    model = openai_config.get('model', 'gpt-4o-mini')
    base_url = openai_config.get('base_url')  # None = OpenAI, or OpenRouter URL

    if not api_key and not args.dry_run:
        logger.error("API key not found in config or environment")
        sys.exit(1)

    logger.info(f"Using model: {model}, base_url: {base_url or 'OpenAI'}, workers: {args.workers}")

    # Paths
    raw_data_dir = Path("data/raw")
    output_dir = Path("data/extracted")

    # Get tickers
    if args.ticker:
        tickers = [args.ticker]
    else:
        tickers = get_all_tickers(universe)

    logger.info(f"Processing {len(tickers)} tickers")

    # Count filings
    filing_counts = count_filings(raw_data_dir, tickers)
    total_filings = sum(filing_counts.values())
    logger.info(f"Total filings to process: {total_filings}")

    # Count already extracted
    extracted_counts = count_extracted(output_dir, tickers)
    total_extracted = sum(extracted_counts.values())
    logger.info(f"Already extracted: {total_extracted}")

    if args.resume:
        remaining = total_filings - total_extracted
        logger.info(f"Remaining to extract: {remaining}")

    # Dry run - just show stats
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - No API calls will be made")
        print("=" * 60)
        print(f"Tickers: {len(tickers)}")
        print(f"Total filings: {total_filings}")
        print(f"Already extracted: {total_extracted}")

        to_process = total_filings - total_extracted if args.resume else total_filings
        print(f"To process: {to_process}")

        # Estimate cost
        sample_tokens = 8000  # Average tokens per filing
        output_tokens = 1500  # Average output tokens

        cost_per_file = estimate_cost(sample_tokens, output_tokens)
        total_cost = cost_per_file * to_process

        print(f"\nEstimated cost: ${total_cost:.2f}")
        print("(based on ~8K input tokens, ~1.5K output tokens per filing)")
        return

    # Test mode
    if args.test:
        test_files = select_test_files(raw_data_dir, tickers, n=10)
        logger.info(f"Test mode: processing {len(test_files)} files")

        extractor = FilingExtractor(api_key=api_key, model=model, base_url=base_url, incidents_dir=output_dir, max_workers=args.workers)

        for ticker, filing_path in tqdm(test_files, desc="Extracting"):
            filename = filing_path.stem
            parts = filename.split('_')
            filing_type = parts[0]
            filing_date = parts[1]

            logger.info(f"Processing {ticker} {filing_type} {filing_date}")

            facts = extractor.extract_from_file(
                filing_path=filing_path,
                ticker=ticker,
                filing_type=filing_type,
                filing_date=filing_date
            )

            if facts:
                # Save
                ticker_dir = output_dir / ticker
                ticker_dir.mkdir(parents=True, exist_ok=True)
                output_file = ticker_dir / f"{filing_type}_{filing_date}.json"

                with open(output_file, 'w') as f:
                    json.dump(facts.model_dump(), f, indent=2)

                logger.info(f"Saved: {output_file}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print(extractor.cost_tracker.summary())
        return

    # Full extraction
    extractor = FilingExtractor(api_key=api_key, model=model, base_url=base_url, incidents_dir=output_dir, max_workers=args.workers)

    processed = 0
    for ticker in tqdm(tickers, desc="Tickers"):
        filings_dir = raw_data_dir / ticker / "filings"

        if not filings_dir.exists():
            continue

        results = extractor.extract_batch(
            filings_dir=filings_dir,
            ticker=ticker,
            output_dir=output_dir,
            resume=args.resume
        )

        processed += len(results)

        if args.limit and processed >= args.limit:
            logger.info(f"Reached limit of {args.limit} files")
            break

    # Final summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(extractor.cost_tracker.summary())
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
