import logging
from anonymization.app.anonymizer import AnonymizationService

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_e_names():
    """Test name detection for names starting with E."""
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
    
    print("=== Names Starting with E Test ===")
    for text in e_names:
        # Extract the name from the beginning of the sentence
        name = text.split()[0]
        
        # Test with analyzer
        results = service.analyzer.analyze(text=text, language="de")
        
        if results:
            detected_names = []
            for result in results:
                detected_name = text[result.start:result.end]
                detected_names.append(f"{detected_name} ({result.entity_type}, Score: {result.score:.2f})")
            
            print(f"✓ In '{text}' detected: {', '.join(detected_names)}")
        else:
            print(f"✗ Failed to detect name in: '{text}' (Expected: {name})")

if __name__ == "__main__":
    # Test names starting with E
    test_e_names()
    
    print("\n=== Test Complete ===")
