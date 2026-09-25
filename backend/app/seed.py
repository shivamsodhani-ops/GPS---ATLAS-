"""First-run bootstrap: default departments + an admin account, and
(optionally) a handful of demo documents so a fresh install has something to
search on stage instead of an empty screen.
"""
from __future__ import annotations

import logging

from .config import settings
from .database import SessionLocal
from .models import Department, Document, DocumentVersion, Role, User
from .security import hash_password
from .services import ingestion

logger = logging.getLogger("atlas.seed")

DEFAULT_DEPARTMENTS = [
    ("Legal", "LEGAL"),
    ("Engineering", "ENG"),
    ("Procurement", "PROC"),
    ("Finance", "FIN"),
    ("Projects", "PROJ"),
    ("Founder's Office", "FO"),
]

DEMO_DOCS = [
    (
        "Vendor Supply Agreement - BioCNG Compressors Ltd",
        "contract",
        "PROC",
        "employee",
        """SUPPLY AGREEMENT between GPS Renewables Private Limited ("GPS") and BioCNG Compressors Ltd ("Vendor").
This agreement governs the supply of 12 biogas compression units for the Ramanagara project.
Contract Value: INR 84,50,000 (Eighty Four Lakh Fifty Thousand only), payable in three milestones.
Delivery Timeline: All units to be delivered within 90 days of purchase order date.
Warranty: 24 months from date of commissioning, covering manufacturing defects only.
Valid until: 31 March 2027.
Termination Date: This agreement may be terminated by either party with 60 days written notice.
Governing Law: This agreement is governed by the laws of India, with jurisdiction in Bengaluru courts.
Confidentiality: Both parties agree to keep commercial terms confidential for 3 years post termination.
""",
    ),
    (
        "Weekly Progress Report - Ramanagara Biogas Plant - Week 34",
        "progress_report",
        "PROJ",
        "employee",
        """WEEKLY PROGRESS REPORT: Ramanagara Biogas Plant, Week 34, 2026.
Overall project completion: 68%.
Civil works: Digester tank foundation complete. Slurry pit lining in progress, 2 days behind schedule due to monsoon delays.
Mechanical: Compressor units awaited from BioCNG Compressors Ltd, expected delivery per PO GPS-PO-2026-0417.
Commercial risk flagged: vendor has requested a 15-day extension citing raw material shortage; Procurement to review against the penalty clause in the supply agreement.
Safety: Zero lost-time incidents this week. One near-miss reported and closed with corrective action.
Manpower: 42 workers on site, average attendance 91%.
Next week priorities: complete slurry pit lining, begin piping fabrication, follow up with vendor on compressor delivery date.
""",
    ),
    (
        "Minutes of Meeting - Founder's Office Review - Ramanagara",
        "mom",
        "FO",
        "manager",
        """MINUTES OF MEETING: Founder's Office Monthly Review, Ramanagara Biogas Plant.
Attendees: Founder's Office, Head of Projects, Head of Procurement.
Discussion: The Ramanagara project is currently 68% complete against a planned 75%, a 7% slippage attributed to monsoon delays and a pending compressor delivery from BioCNG Compressors Ltd.
Decision: Procurement to issue a formal notice to the vendor referencing the delivery timeline in the supply agreement and evaluate the penalty clause if the 15-day extension request is not justified.
Decision: Projects to submit a revised completion forecast by next Friday.
Action Item: Founder's Office requested a consolidated view of all vendor contracts with delivery obligations due in the next 60 days across all active projects.
Next review scheduled in four weeks.
""",
    ),
    (
        "GPS ATLAS - Access Control & Data Security Policy",
        "policy",
        "FO",
        "",
        """GPS ATLAS DATA SECURITY POLICY.
All documents uploaded to ATLAS are encrypted at rest using authenticated encryption; the encryption key never leaves the server and is never stored in the database itself.
Every document carries a Viewer ID scope: it is visible only to its owning department, any explicitly granted departments or roles, or an individual explicitly granted access by a manager or administrator.
The AI search assistant applies this same Viewer ID scope before it retrieves a single sentence of text; a user can never receive an AI summary built from a document they are not authorized to open directly.
Every AI-generated answer is passed through a Citation Verification Layer: any claim without a citation linking it back to a retrieved, authorized source document is flagged to the user as unverified rather than presented as fact.
All logins, uploads, downloads, searches and administrative actions are recorded in an immutable audit log reviewable by administrators.
Passwords are hashed with bcrypt and are never stored or logged in plain text. Repeated failed login attempts temporarily lock the account.
This policy applies to every department: Legal, Engineering, Procurement, Finance, Projects and the Founder's Office.
""",
    ),
]


def run_seed() -> None:
    db = SessionLocal()
    try:
        dept_by_code: dict[str, Department] = {}
        for name, code in DEFAULT_DEPARTMENTS:
            existing = db.query(Department).filter(Department.code == code).first()
            if not existing:
                existing = Department(name=name, code=code)
                db.add(existing)
                db.flush()
            dept_by_code[code] = existing
        db.commit()

        admin = db.query(User).filter(User.email == settings.seed_admin_email.lower()).first()
        if not admin:
            admin = User(
                name="ATLAS Administrator",
                email=settings.seed_admin_email.lower(),
                hashed_password=hash_password(settings.seed_admin_password),
                role=Role.ADMIN,
                department_id=dept_by_code["FO"].id,
                must_change_password=True,
            )
            db.add(admin)
            db.commit()
            logger.warning(
                "Seeded default admin account %s -- CHANGE THIS PASSWORD IMMEDIATELY after first login.",
                settings.seed_admin_email,
            )

        if not settings.seed_demo_data:
            return
        if db.query(Document).count() > 0:
            return  # demo data already populated (or real data has been uploaded)

        for title, doc_type, dept_code, allowed_role, text in DEMO_DOCS:
            dept = dept_by_code[dept_code]
            doc = Document(
                title=title,
                doc_type=doc_type,
                description="Seed/demo document for first-run evaluation.",
                tags="[\"demo\"]",
                department_id=dept.id,
                allowed_roles=f'["{allowed_role}"]' if allowed_role else "[]",
                uploader_id=admin.id,
            )
            db.add(doc)
            db.flush()

            raw_bytes = text.encode("utf-8")
            storage_path, sha256 = ingestion.store_upload(raw_bytes, f"{title}.txt")
            version = DocumentVersion(
                document_id=doc.id,
                version_number=1,
                original_filename=f"{title}.txt",
                mime_type="text/plain",
                file_size_bytes=len(raw_bytes),
                storage_path=storage_path,
                sha256=sha256,
                uploaded_by=admin.id,
            )
            db.add(version)
            db.flush()
            doc.current_version_id = version.id
            db.commit()
            db.refresh(version)
            db.refresh(doc)
            ingestion.process_new_version(db, doc, version, raw_bytes)

        logger.info("Seeded %d demo documents.", len(DEMO_DOCS))
    finally:
        db.close()
