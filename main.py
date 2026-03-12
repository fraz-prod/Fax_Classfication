"""
ECW Fax Downloader - Main Orchestrator
Automates ECW fax inbox navigation and downloads PDFs locally.
"""

import asyncio
import logging
from datetime import datetime
from ecw_bot import ECWBot
from pdf_handler import PDFHandler
from logger import FaxLogger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'logs/agent_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


async def main():
    log.info("=" * 60)
    log.info("   ECW FAX DOWNLOADER STARTING")
    log.info("=" * 60)

    bot = ECWBot()
    pdf_handler = PDFHandler()
    fax_logger = FaxLogger()

    try:
        # Step 1: Launch browser and login to ECW
        log.info("Launching browser and logging into ECW...")
        await bot.launch()
        await bot.login()

        # Step 2: Open Fax Inbox
        log.info("Opening Fax Inbox Web Mode...")
        await bot.open_fax_inbox()

        # Step 3: Select today's date
        log.info("Selecting today's date...")
        await bot.select_date(datetime.today())

        # Step 4: Get list of all faxes
        fax_list = await bot.get_fax_list()
        log.info(f"Found {len(fax_list)} faxes to process today.")

        results = []

        # Step 5: Process each fax
        for i, fax in enumerate(fax_list):
            log.info(f"\n--- Processing fax {i+1} of {len(fax_list)} ---")
            fax_id = f"fax_{i+1}_{datetime.now().strftime('%H%M%S')}"

            # Download PDF bytes from ECW preview
            log.info("Downloading PDF from ECW...")
            pdf_bytes = await bot.download_fax_pdf(fax)

            if not pdf_bytes:
                log.warning(f"  Could not download PDF for fax {i+1} — skipping.")
                results.append({
                    'fax_index': i + 1,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'FAILED',
                    'filepath': '',
                    'reason': 'Could not read ECW preview iframe'
                })
                continue

            # Save PDF locally
            log.info("Saving PDF locally...")
            filepath = pdf_handler.save_pdf(pdf_bytes, fax_id)

            log.info(f"✅ Success: Saved to {filepath}")
            
            # Log result
            results.append({
                'fax_index': i + 1,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'SUCCESS',
                'filepath': filepath,
                'reason': ''
            })

        # Step 6: Save audit log to Excel
        fax_logger.save(results)
        log.info(f"\nDone! Downloaded {len([r for r in results if r['status'] == 'SUCCESS'])} faxes. Log saved.")

    except Exception as e:
        log.error(f"Agent crashed: {e}", exc_info=True)

    finally:
        await bot.close()
        log.info("Browser closed. Agent finished.")


if __name__ == "__main__":
    asyncio.run(main())
