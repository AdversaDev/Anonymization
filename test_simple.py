import re
from anonymization.app.anonymizer import DATE_REGEX

# Test abbreviated month names
print("=== Testing Abbreviated Month Names ===")
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
        print(f"✓ Matched: {date}")
    else:
        print(f"✗ Failed to match: {date}")

print("\n=== Test Complete ===")
