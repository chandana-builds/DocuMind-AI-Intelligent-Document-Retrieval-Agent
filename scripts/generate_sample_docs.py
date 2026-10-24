"""Generate sample test documents for DocuMind AI.

Creates clearly fictional sample documents:
1. sample_documents/fictional_leave_policy.pdf (2 pages)
2. sample_documents/fictional_internship_handbook.pdf (2 pages)
3. sample_documents/fictional_reimbursement_policy.txt
"""

import os
import pymupdf


def generate_documents(output_dir: str = "sample_documents"):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Fictional Leave Policy (PDF, 2 pages)
    pdf_leave_path = os.path.join(output_dir, "fictional_leave_policy.pdf")
    doc_leave = pymupdf.open()

    # Page 1
    page1 = doc_leave.new_page(width=595, height=842)  # A4 size
    p1_text = """AURA CLOUD TECHNOLOGIES — INTERNAL LEAVE POLICY (FICTIONAL)
Document Reference: POL-HR-2026-04
Effective Date: January 1, 2026
Applicability: All Full-Time Global Employees

1. Annual Paid Time Off (PTO)
Aura Cloud Technologies provides 28 days of fully paid annual leave to all full-time regular employees per calendar year. Annual leave accrues at the rate of 2.33 days per completed month of active employment.
Employees may carry over a maximum of 5 unused annual leave days into the subsequent calendar year. Any unused days exceeding 5 will expire on March 31 without cash compensation.

2. Sick and Wellness Leave
Employees receive 10 days of dedicated medical and mental wellness leave each year. A medical practitioner certificate is mandatory for any continuous sick leave absence exceeding 3 consecutive business days.

3. Parental and Family Care Leave
Primary caregivers are entitled to 16 weeks of fully paid parental leave following birth, adoption, or foster placement. Secondary caregivers receive 6 weeks of fully paid leave.
"""
    page1.insert_text((50, 60), p1_text, fontsize=11, lineheight=1.4)

    # Page 2
    page2 = doc_leave.new_page(width=595, height=842)
    p2_text = """AURA CLOUD TECHNOLOGIES — INTERNAL LEAVE POLICY (PAGE 2)

4. Bereavement and Compassionate Leave
Employees are granted up to 5 consecutive paid business days for immediate family members (spouse, child, parent, sibling), and up to 3 days for extended family.

5. Sabbatical Leave
Employees with five or more consecutive years of service at Aura Cloud Technologies may apply for an unpaid sabbatical of up to 3 months. Applications must be submitted to People Ops at least 60 days in advance.

6. Leave Request and Approval Protocol
All planned leave requests must be submitted through the Aura HR Portal at least 10 business days before the intended start date for leave exceeding 3 days. Unplanned emergency leave must be communicated to the direct manager by 9:00 AM local time on the day of absence.
"""
    page2.insert_text((50, 60), p2_text, fontsize=11, lineheight=1.4)
    doc_leave.save(pdf_leave_path)
    doc_leave.close()
    print(f"Generated: {pdf_leave_path}")

    # 2. Fictional Internship Handbook (PDF, 2 pages)
    pdf_intern_path = os.path.join(output_dir, "fictional_internship_handbook.pdf")
    doc_intern = pymupdf.open()

    # Page 1
    page1 = doc_intern.new_page(width=595, height=842)
    p1_text = """NEXUS ROBOTICS LABS — INTERNSHIP PROGRAM HANDBOOK (FICTIONAL)
Program Term: Summer Cohort 2026
Target Audience: Graduate & Undergraduate Engineering Interns

1. Program Duration and Weekly Commitment
The Nexus Robotics Summer Internship runs for 12 continuous weeks, starting June 1 and ending August 21. Interns are expected to work 40 hours per week, Monday through Friday, between 9:00 AM and 5:00 PM EST.

2. Mentorship and Mid-Term Milestones
Every intern is paired with a Principal Robotics Engineer as their Technical Mentor. Interns must complete a formal Mid-Term Project Review at Week 6. Successful mid-term defense is a prerequisite for project capstone funding.

3. Equipment and Hardware Security
Interns will be provisioned a Nexus Secure Developer Laptop and hardware evaluation boards. Hardware may not leave the secure research lab premises without signed authorization from the Lab Director.
"""
    page1.insert_text((50, 60), p1_text, fontsize=11, lineheight=1.4)

    # Page 2
    page2 = doc_intern.new_page(width=595, height=842)
    p2_text = """NEXUS ROBOTICS LABS — INTERNSHIP HANDBOOK (PAGE 2)

4. Monthly Stipend and Housing Allowance
Interns receive a competitive monthly educational stipend of $5,200. For interns relocating from more than 50 miles away from our Boston research facility, Nexus Robotics provides a one-time relocation stipend of $2,000 and corporate housing assistance.

5. Final Capstone Presentation and Return Offer Criteria
During Week 11, interns will showcase their research artifacts during Demo Day to company executive leadership. Interns who achieve an 'Exceeds Expectations' rating across their technical mentor evaluation and capstone presentation will receive a pre-graduation full-time return offer by September 15.

6. Code of Conduct and Intellectual Property
All code, models, and schematics developed during the internship remain the exclusive intellectual property of Nexus Robotics Labs. Interns may publish academic preprints based on their work only after obtaining written IP clearance from the Legal Office.
"""
    page2.insert_text((50, 60), p2_text, fontsize=11, lineheight=1.4)
    doc_intern.save(pdf_intern_path)
    doc_intern.close()
    print(f"Generated: {pdf_intern_path}")

    # 3. Fictional Reimbursement Policy (TXT)
    txt_reimb_path = os.path.join(output_dir, "fictional_reimbursement_policy.txt")
    reimb_text = """ZENITH GLOBAL CONSULTING — BUSINESS EXPENSE REIMBURSEMENT POLICY (FICTIONAL)
Document Code: POL-FIN-2026-EXP
Revision: 3.2 | Effective Date: February 2026

1. Purpose and Scope
This policy defines allowable expenses and reimbursement procedures for business travel, client meals, and home office setups incurred by Zenith Global Consulting associates.

2. Daily Meal Allowances (Per Diem)
- Domestic Travel: Up to $75 per day ($15 Breakfast, $25 Lunch, $35 Dinner).
- International Travel: Up to $110 per day.
- Itemized receipts are mandatory for all individual meal charges exceeding $25. Alcoholic beverages are not reimbursable unless part of an authorized client dinner pre-approved by a Managing Director.

3. Flight and Lodging Guidelines
- Air Travel: Economy class is standard for all flights under 6 hours duration. Business class is permitted for continuous international flights exceeding 6 hours.
- Hotel Lodging: Maximum room rate is capped at $250 per night in standard tier cities and $350 per night in designated high-cost metropolitan centers (e.g., New York, London, Tokyo, San Francisco).

4. Remote Work and Home Office Allowance
Full-time remote associates receive a one-time setup stipend of $1,000 for ergonomic furniture and dual monitors, plus a monthly internet stipend of $80.

5. Submission Deadlines and Approval Hierarchy
All expense reports must be submitted via Concur within 30 calendar days of expense occurrence. Claims submitted after 60 days will be automatically rejected. Expenses up to $1,000 require Manager approval; expenses exceeding $1,000 require Department Head approval. Approved reimbursements are deposited in the next bi-weekly payroll cycle.
"""
    with open(txt_reimb_path, "w", encoding="utf-8") as f:
        f.write(reimb_text)
    print(f"Generated: {txt_reimb_path}")


if __name__ == "__main__":
    generate_documents()
