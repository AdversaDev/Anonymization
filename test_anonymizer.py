import sys
import logging
from anonymization.app.anonymizer import AnonymizationService, detect_dates, DATE_REGEX, detect_license_plates, LICENSE_PLATE_REGEX
import uuid
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_date_regex():
    """Test the DATE_REGEX pattern directly with various date formats."""
    test_dates = [
        # Full month names
        "15. Januar 1910",
        "15 Januar 1910",
        "01. März 2022",
        "1 April 1999",
        # Abbreviated month names
        "15. Jan. 1910",
        "15 Jan 1910",
        "01. Mär. 2022",
        "1 Apr 1999",
        # Numeric formats
        "15-03-2023",
        "2023-03-15",
        "15/03/2023",
        "15.03.2023",
        "15.03.23"
    ]
    
    logger.info("Testing DATE_REGEX pattern...")
    for date in test_dates:
        matches = re.findall(DATE_REGEX, date)
        if matches:
            logger.info(f"✓ Matched: {date}")
        else:
            logger.error(f"✗ Failed to match: {date}")

def test_license_plate_regex():
    """Test the LICENSE_PLATE_REGEX pattern directly with various license plate formats."""
    test_plates = [
        "M AB 123",
        "B C 1",
        "HH AB 1234",
        "MÜ X 99",
        "S-XY 123",
        "BN-Z 7"
    ]
    
    logger.info("\nTesting LICENSE_PLATE_REGEX pattern...")
    for plate in test_plates:
        matches = re.findall(LICENSE_PLATE_REGEX, plate)
        if matches:
            logger.info(f"✓ Matched: {plate}")
        else:
            logger.error(f"✗ Failed to match: {plate}")

def test_detect_dates():
    """Test the detect_dates function with various date formats."""
    test_texts = [
        # Full month names
        "Ich bin am 15. Januar 1910 geboren.",
        "Ich bin am 15 Januar 1910 geboren.",
        "Das Treffen findet am 01. März 2022 statt.",
        "Das Treffen findet am 1 April 1999 statt.",
        # Abbreviated month names
        "Ich bin am 15. Jan. 1910 geboren.",
        "Ich bin am 15 Jan 1910 geboren.",
        "Das Treffen findet am 01. Mär. 2022 statt.",
        "Das Treffen findet am 1 Apr 1999 statt.",
        # Numeric formats
        "Termin: 15-03-2023",
        "Datum: 2023-03-15",
        "Fälligkeitsdatum: 15/03/2023",
        "Geburtsdatum: 15.03.2023",
        "Geboren am 15.03.23"
    ]
    
    logger.info("\nTesting detect_dates function...")
    for text in test_texts:
        results = detect_dates(text)
        if results:
            for result in results:
                detected_date = text[result.start:result.end]
                logger.info(f"✓ Detected in '{text}': {detected_date}")
        else:
            logger.error(f"✗ Failed to detect date in: {text}")

def test_detect_license_plates():
    """Test the detect_license_plates function with various license plate formats."""
    test_texts = [
        "Mein Auto hat das Kennzeichen M AB 123.",
        "Das Fahrzeug mit dem Kennzeichen B C 1 parkt dort.",
        "HH AB 1234 ist das Kennzeichen meines Autos.",
        "Das Auto mit dem Kennzeichen MÜ X 99 gehört mir.",
        "Ich habe ein Auto mit dem Kennzeichen S-XY 123.",
        "BN-Z 7 ist das Kennzeichen meines Motorrads."
    ]
    
    logger.info("\nTesting detect_license_plates function...")
    for text in test_texts:
        results = detect_license_plates(text)
        if results:
            for result in results:
                detected_plate = text[result.start:result.end]
                logger.info(f"✓ Detected in '{text}': {detected_plate}")
        else:
            logger.error(f"✗ Failed to detect license plate in: {text}")

def test_anonymization_service():
    """Test the full anonymization service with various date formats, license plates, and names."""
    service = AnonymizationService()
    test_session = str(uuid.uuid4())
    
    test_texts = [
        # Test dates
        "Ich bin am 15. Januar 1910 geboren und wohne in Hauptstraße 123.",
        "Ich bin am 15 Januar 1910 geboren und wohne in Hauptstraße 123.",
        
        # Test license plates
        "Mein Auto hat das Kennzeichen M AB 123 und ich wohne in Berlin.",
        "Das Fahrzeug mit dem Kennzeichen B C 1 parkt in München.",
        
        # Test names (including those starting with E and ending with a)
        "Mein Name ist Eva und ich wohne in Hamburg.",
        "Emma und Thomas sind meine Freunde.",
        "Elisa ist meine Schwester und sie wohnt in Frankfurt.",
        "Elena und Michael arbeiten zusammen in Stuttgart.",
        
        # Test combination of different entities
        "Mein Name ist Elisa, ich wohne in Hauptstraße 123, 10115 Berlin, " +
        "mein Geburtsdatum ist 15.03.1985, meine Telefonnummer ist +49 170 1234567 " +
        "und mein Auto hat das Kennzeichen B AB 123."
    ]
    
    logger.info("\nTesting full anonymization service...")
    for text in test_texts:
        logger.info(f"\nOriginal: {text}")
        try:
            anonymized = service.anonymize_text(test_session, text)
            logger.info(f"Anonymized: {anonymized}")
            
            # Show which parts were anonymized
            for original, anonymized_text in zip([text], [anonymized]):
                # Find all tokens in the anonymized text (format: anno_XXXXXXXX)
                anon_tokens = re.findall(r'anno_[a-f0-9]{8}', anonymized_text)
                
                if anon_tokens:
                    logger.info("Anonymized entities:")
                    conn = service.get_db_connection()
                    cursor = conn.cursor()
                    
                    for token in anon_tokens:
                        cursor.execute(
                            "SELECT original_value, entity_type FROM anonymization WHERE anon_id = %s AND session_id = %s",
                            (token, test_session)
                        )
                        result = cursor.fetchone()
                        if result:
                            original_value, entity_type = result
                            logger.info(f"  - {token} ({entity_type}): {original_value}")
                    
                    cursor.close()
                    conn.close()
            
            deanonymized = service.deanonymize_text(test_session, anonymized)
            logger.info(f"Deanonymized: {deanonymized}")
            
            if deanonymized == text:
                logger.info("✓ Successful round-trip")
            else:
                logger.error(f"✗ Round-trip failed: original and deanonymized texts don't match")
        except Exception as e:
            logger.error(f"Error during anonymization test: {e}")

def test_name_detection():
    """Test the name detection, especially for names starting with E and ending with a."""
    service = AnonymizationService()
    
    test_texts = [
        "Mein Name ist Eva.",
        "Emma ist meine Freundin.",
        "Elisa wohnt in Berlin.",
        "Elena arbeitet in München.",
        "Erika und Thomas sind verheiratet.",
        "Meine Schwester heißt Emilia.",
        "Ella und Anna sind Schwestern.",
        "Elisabeth ist meine Tante.",
        "Erica ist eine amerikanische Variante von Erika.",
        "Ewa ist die polnische Form von Eva."
    ]
    
    logger.info("\nTesting name detection (especially E*a names)...")
    for text in test_texts:
        results = service.analyzer.analyze(text=text, language="de", entities=["PERSON"])
        if results:
            for result in results:
                detected_name = text[result.start:result.end]
                logger.info(f"✓ Detected in '{text}': {detected_name} (Score: {result.score})")
        else:
            logger.error(f"✗ Failed to detect name in: {text}")

# Create a mock database connection for local testing
class MockDBConnection:
    """Mock database connection for local testing without Docker."""
    def __init__(self):
        self.data = {}
        
    def cursor(self):
        return MockCursor(self)
        
    def commit(self):
        pass
        
    def close(self):
        pass

class MockCursor:
    """Mock cursor for local testing without Docker."""
    def __init__(self, connection):
        self.connection = connection
        
    def execute(self, query, params=None):
        if "INSERT INTO" in query:
            session_id, anon_id, original_value, entity_type = params
            if session_id not in self.connection.data:
                self.connection.data[session_id] = {}
            self.connection.data[session_id][anon_id] = (original_value, entity_type)
        elif "SELECT" in query:
            self.last_query = query
            self.last_params = params
            
    def fetchall(self):
        if "SELECT anon_id, original_value FROM" in self.last_query:
            session_id = self.last_params[0]
            if session_id in self.connection.data:
                return [(anon_id, original_value) for anon_id, (original_value, _) in self.connection.data[session_id].items()]
            return []
        elif "SELECT original_value, entity_type FROM" in self.last_query:
            anon_id, session_id = self.last_params
            if session_id in self.connection.data and anon_id in self.connection.data[session_id]:
                return [self.connection.data[session_id][anon_id]]
            return []
        return []
        
    def fetchone(self):
        results = self.fetchall()
        if results:
            return results[0]
        return None
        
    def close(self):
        pass

def test_anonymization_service_local():
    """Test the full anonymization service locally without Docker."""
    # Import the get_db_connection function from anonymizer.py
    from anonymization.app.anonymizer import get_db_connection
    
    # Save the original function and replace it with our mock
    original_get_db_connection = get_db_connection
    
    # Define a replacement function that returns our mock connection
    def mock_get_db_connection():
        return MockDBConnection()
    
    # Monkey patch the module
    import anonymization.app.anonymizer
    anonymization.app.anonymizer.get_db_connection = mock_get_db_connection
    
    service = AnonymizationService()
    test_session = str(uuid.uuid4())
    
    test_texts = [
        # Test dates with full and abbreviated month names
        "Ich bin am 15. Januar 1910 geboren.",
        "Ich bin am 15 Jan 1910 geboren.",
        
        # Test license plates
        "Mein Auto hat das Kennzeichen M AB 123.",
        
        # Test names (including those starting with E and ending with a)
        "Mein Name ist Eva und ich wohne in Hamburg.",
        "Emma und Thomas sind meine Freunde.",
        "Elisa ist meine Schwester und sie wohnt in Frankfurt.",
        "Elena arbeitet in München.",
        
        # Test combination of different entities
        "Mein Name ist Elisa, ich wohne in Hauptstraße 123, 10115 Berlin, " +
        "mein Geburtsdatum ist 15. Jan. 1985, meine Telefonnummer ist +49 170 1234567 " +
        "und mein Auto hat das Kennzeichen B AB 123."
    ]
    
    logger.info("\nTesting full anonymization service locally...")
    for text in test_texts:
        logger.info(f"\nOriginal: {text}")
        try:
            anonymized = service.anonymize_text(test_session, text)
            logger.info(f"Anonymized: {anonymized}")
            
            # Show which parts were anonymized
            anon_tokens = re.findall(r'anno_[a-f0-9]{8}', anonymized)
            
            if anon_tokens:
                logger.info("Anonymized entities:")
                conn = mock_get_db_connection()
                
                for token in anon_tokens:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT original_value, entity_type FROM anonymization WHERE anon_id = %s AND session_id = %s",
                        (token, test_session)
                    )
                    result = cursor.fetchone()
                    if result:
                        original_value, entity_type = result
                        logger.info(f"  - {token} ({entity_type}): {original_value}")
                    cursor.close()
            
            deanonymized = service.deanonymize_text(test_session, anonymized)
            logger.info(f"Deanonymized: {deanonymized}")
            
            if deanonymized == text:
                logger.info("✓ Successful round-trip")
            else:
                logger.error(f"✗ Round-trip failed: original and deanonymized texts don't match")
        except Exception as e:
            logger.error(f"Error during anonymization test: {e}")
    
    # Restore the original get_db_connection function
    anonymization.app.anonymizer.get_db_connection = original_get_db_connection

if __name__ == "__main__":
    # Clear previous output
    print("\n" * 10)
    
    logger.info("=== Abbreviated Month Names Test ===")
    # Test abbreviated month names
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
    
    for date in abbreviated_dates:
        matches = re.findall(DATE_REGEX, date)
        if matches:
            logger.info(f"✓ Matched abbreviated date: {date}")
        else:
            logger.error(f"✗ Failed to match abbreviated date: {date}")
    
    logger.info("\n=== Names Starting with E and Ending with A Test ===")
    # Test names starting with E and ending with a
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
    
    for text in e_names:
        results = service.analyzer.analyze(text=text, language="de", entities=["PERSON"])
        if results:
            for result in results:
                detected_name = text[result.start:result.end]
                logger.info(f"✓ Detected name: {detected_name} in '{text}' (Score: {result.score:.2f})")
        else:
            logger.error(f"✗ Failed to detect name in: {text}")
    
    logger.info("\n=== Test Complete ===")
