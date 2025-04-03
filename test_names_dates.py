import logging
import re
from anonymization.app.anonymizer import AnonymizationService, DATE_REGEX

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_abbreviated_month_names():
    """Test the DATE_REGEX pattern with abbreviated month names."""
    abbreviated_dates = [
        "15. Jan. 1910",
        "15 Jan 1910",
        "01. Feb. 2022",
        "1 Mär 1999",
        "30 Apr 2020",
        "12. Mai. 2015",
        "5 Jun 2018",
        "22. Jul. 2005",
        "8 Aug 2010",
        "17. Sep. 2012",
        "3 Okt 2000",
        "25. Nov. 1995",
        "31 Dez 2021"
    ]
    
    logger.info("=== Abbreviated Month Names Test ===")
    for date in abbreviated_dates:
        matches = re.findall(DATE_REGEX, date)
        if matches:
            logger.info(f"✓ Matched: {date}")
        else:
            logger.error(f"✗ Failed to match: {date}")

def test_e_names():
    """Test name detection for names starting with E and ending with a."""
    service = AnonymizationService()
    
    e_names = [
        "Eva ist meine Schwester.",
        "Emma arbeitet als Ärztin.",
        "Elisa studiert in Berlin.",
        "Elena kommt aus München.",
        "Ella spielt Klavier.",
        "Erika ist Lehrerin.",
        "Emilia hat zwei Kinder.",
        "Elisabeth wohnt in Hamburg.",
        "Ewa ist polnischer Herkunft.",
        "Eleonora ist eine italienische Variante."
    ]
    
    logger.info("\n=== Names Starting with E Test ===")
    for text in e_names:
        # Extract the name from the beginning of the sentence
        name = text.split()[0]
        
        # Test with NLP engine
        results = service.analyzer.analyze(text=text, language="de", entities=["PERSON"])
        
        if results:
            for result in results:
                detected_name = text[result.start:result.end]
                logger.info(f"✓ Detected: {detected_name} (Score: {result.score:.2f}) in '{text}'")
        else:
            logger.error(f"✗ Failed to detect name in: '{text}' (Expected: {name})")

if __name__ == "__main__":
    # Test abbreviated month names
    test_abbreviated_month_names()
    
    # Test names starting with E and ending with a
    test_e_names()
    
    logger.info("\n=== Test Complete ===")
