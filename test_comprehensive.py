import re
import logging
from anonymization.app.anonymizer import AnonymizationService, DATE_REGEX, LICENSE_PLATE_REGEX, E_NAMES

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_all_date_formats():
    """Test all date formats including abbreviated month names."""
    dates = [
        # Full month names with dot
        "15. Januar 1910", "01. Februar 2022", "10. März 2000", "5. April 1999",
        "20. Mai 2015", "30. Juni 2018", "25. Juli 2005", "18. August 2010",
        "7. September 2012", "31. Oktober 2000", "15. November 1995", "24. Dezember 2021",
        
        # Full month names without dot
        "15 Januar 1910", "01 Februar 2022", "10 März 2000", "5 April 1999",
        "20 Mai 2015", "30 Juni 2018", "25 Juli 2005", "18 August 2010",
        "7 September 2012", "31 Oktober 2000", "15 November 1995", "24 Dezember 2021",
        
        # Abbreviated month names with dot
        "15. Jan. 1910", "01. Feb. 2022", "10. Mär. 2000", "5. Apr. 1999",
        "20. Mai. 2015", "30. Jun. 2018", "25. Jul. 2005", "18. Aug. 2010",
        "7. Sep. 2012", "31. Okt. 2000", "15. Nov. 1995", "24. Dez. 2021",
        
        # Abbreviated month names without dot
        "15 Jan 1910", "01 Feb 2022", "10 Mär 2000", "5 Apr 1999",
        "20 Mai 2015", "30 Jun 2018", "25 Jul 2005", "18 Aug 2010",
        "7 Sep 2012", "31 Okt 2000", "15 Nov 1995", "24 Dez 2021",
        
        # Numeric formats
        "15-03-2023", "2023-03-15", "15/03/2023", "15.03.2023", "15.03.23"
    ]
    
    print("=== Testing All Date Formats ===")
    for date in dates:
        matches = re.findall(DATE_REGEX, date)
        if matches:
            print(f"✓ Matched: {date}")
        else:
            print(f"✗ Failed to match: {date}")

def test_license_plates():
    """Test license plate recognition."""
    plates = [
        "M AB 123", "B C 1", "HH AB 1234", "MÜ X 99", "S-XY 123", "BN-Z 7",
        "F AB 123", "K XY 789", "DD AB 123", "L-P 42", "HB AB 555"
    ]
    
    print("\n=== Testing License Plate Recognition ===")
    for plate in plates:
        matches = re.findall(LICENSE_PLATE_REGEX, plate)
        if matches:
            print(f"✓ Matched: {plate}")
        else:
            print(f"✗ Failed to match: {plate}")

def test_e_names_recognition():
    """Test recognition of names starting with E."""
    print("\n=== Testing E-Names Recognition ===")
    for name in E_NAMES:
        text = f"{name} ist eine Person."
        service = AnonymizationService()
        results = service.analyzer.analyze(text=text, language="de")
        
        detected = False
        for result in results:
            detected_text = text[result.start:result.end]
            if detected_text == name:
                print(f"✓ Detected: {name} ({result.entity_type}, Score: {result.score:.2f})")
                detected = True
                break
        
        if not detected:
            print(f"✗ Failed to detect: {name}")

def test_full_anonymization():
    """Test full anonymization with various entities."""
    service = AnonymizationService()
    
    test_texts = [
        # Test with dates, names, and license plates
        "Eva wurde am 15. Januar 1910 geboren und fährt ein Auto mit dem Kennzeichen M AB 123.",
        "Emma ist am 20 Mai 2015 nach Berlin gezogen und hat das Kennzeichen B C 1.",
        "Elisa hat am 10. Mär. 2000 ihren Führerschein gemacht und fährt ein Auto mit dem Kennzeichen HH AB 1234.",
        "Elena wurde am 5 Apr 1999 in München geboren und hat das Kennzeichen MÜ X 99.",
        
        # Test with multiple entities in one text
        "Mein Name ist Erika, ich wohne in Hauptstraße 123, 10115 Berlin, " +
        "mein Geburtsdatum ist 15. Jan. 1985, meine Telefonnummer ist +49 170 1234567 " +
        "und mein Auto hat das Kennzeichen B AB 123."
    ]
    
    print("\n=== Testing Full Anonymization ===")
    for text in test_texts:
        print(f"\nOriginal: {text}")
        
        # Analyze the text to find entities
        results = service.analyzer.analyze(text=text, language="de")
        
        if results:
            print("Detected entities:")
            for result in results:
                entity_text = text[result.start:result.end]
                print(f"  - {entity_text} ({result.entity_type}, Score: {result.score:.2f})")
        else:
            print("No entities detected!")

if __name__ == "__main__":
    # Run all tests
    test_all_date_formats()
    test_license_plates()
    test_e_names_recognition()
    test_full_anonymization()
    
    print("\n=== All Tests Complete ===")
