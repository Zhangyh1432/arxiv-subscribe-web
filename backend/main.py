import argparse
import logging
from core import arxiv_fetcher, email_sender
from core.history_manager import save_processed_ids
from core.analysis_manager import process_paper_for_email
import os

# Configure logging for the script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_subscription_service(date=None):
    """
    The main logic of the arXiv subscription service.
    Takes an optional date string.
    Returns a dictionary with status and message.
    """
    try:
        logger.info("Fetching papers from arXiv...")
        papers_by_category = arxiv_fetcher.fetch_papers(date_range=date)
        
        all_papers = [p for papers in papers_by_category.values() for p in papers]
        total_papers = len(all_papers)
        logger.info(f"Found {total_papers} total papers.")

        if total_papers > 0:
            logger.info("Processing papers (with caching)... ")
            files_to_zip = []
            # A dummy task_status object for the analysis manager
            task_status = {'message': ''}
            for paper in all_papers:
                # This will use the cache if available, or generate and save a new analysis
                files_to_zip.append(process_paper_for_email(paper, task_status, logger))
            
            logger.info("Sending email notification with zip attachment...")
            email_sent = email_sender.send_email(files_to_zip, total_papers)

            if email_sent:
                # Save all processed papers to the history
                save_processed_ids(all_papers)
                return {"status": "success", "message": f"Process finished. Found and emailed {total_papers} papers."}
            else:
                return {"status": "error", "message": "Email sending failed."}
        else:
            logger.info("No new papers to send.")
            return {"status": "success", "message": "Process finished. No new papers found."}

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == '__main__':
    """
    Allows running the service from the command line.
    """
    parser = argparse.ArgumentParser(description="Fetch and analyze recent papers from arXiv.")
    parser.add_argument("--date", type=str, help="The date range to fetch papers from (e.g., 'last_month'). Defaults to recent.")
    args = parser.parse_args()
    
    result = run_subscription_service(args.date)
    print(result)