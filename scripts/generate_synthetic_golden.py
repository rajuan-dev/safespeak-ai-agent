from pathlib import Path

import fitz


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "legal-golden" / "generated"
    root.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page1 = document.new_page()
    page1.insert_text((72, 60), "Example Safety Act 2026", fontsize=18, fontname="hebo")
    page1.insert_text((72, 88), "As at 21 June 2026", fontsize=10)
    page1.insert_text((72, 120), "Part 1 Preliminary", fontsize=15, fontname="hebo")
    page1.insert_text((72, 150), "1 Short title", fontsize=13, fontname="hebo")
    page1.insert_text((72, 175), "This Act is the Example Safety Act 2026.", fontsize=10)
    page1.insert_text((72, 210), "2 Definitions", fontsize=13, fontname="hebo")
    page1.insert_text(
        (72, 235),
        '(1) "protected record" means a stored incident record.',
        fontsize=10,
    )
    page1.insert_text((72, 270), "3 Reporting duty", fontsize=13, fontname="hebo")
    page1.insert_text((72, 295), "(1) A provider must preserve a protected record.", fontsize=10)
    page1.insert_text((72, 320), "(a) the record must be retained for 7 years;", fontsize=10)
    page1.insert_text((72, 345), "(i) access must be logged.", fontsize=10)

    page2 = document.new_page()
    page2.insert_text((72, 60), "4 Former notice provision", fontsize=13, fontname="hebo")
    page2.insert_text((72, 85), "Repealed by Example Amendment Act 2026.", fontsize=10)
    page2.insert_text((72, 125), "5 Related duties", fontsize=13, fontname="hebo")
    page2.insert_text((72, 150), "See section 3 of the Example Safety Act 2026.", fontsize=10)
    page2.insert_text((72, 195), "Schedule 1 Penalty units", fontsize=15, fontname="hebo")
    page2.insert_text((72, 225), "Item", fontsize=10)
    page2.insert_text((160, 225), "Penalty", fontsize=10)
    page2.insert_text((72, 250), "Failure to preserve", fontsize=10)
    page2.insert_text((160, 250), "50 penalty units", fontsize=10)
    document.save(root / "example-safety-act-2026.pdf")
    document.close()


if __name__ == "__main__":
    main()
