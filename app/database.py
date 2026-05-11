import json
from datetime import date, timedelta

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Customer, Invoice, Job, Payment, Quote
from app.nz_time import nz_naive_now, nz_today

DATABASE_URL = "sqlite:///./garden_local.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def apply_sqlite_migrations(engine) -> None:
    """Add columns introduced after first deploy (SQLite has no ALTER in create_all)."""
    if "sqlite" not in str(engine.url):
        return
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "quotes" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("quotes")}
    with engine.begin() as conn:
        if "line_items_json" not in cols:
            conn.execute(text("ALTER TABLE quotes ADD COLUMN line_items_json TEXT"))
        if "discount_ex_gst" not in cols:
            conn.execute(text("ALTER TABLE quotes ADD COLUMN discount_ex_gst FLOAT"))


def ensure_demo_invoice_if_empty(db: Session) -> None:
    """When DB was created before invoices existed, add a demo row for id 1 (tests / UI)."""
    if db.query(Invoice).count() > 0:
        return
    if db.query(Customer).count() == 0:
        return
    today = nz_today()
    due = date.fromordinal(today.toordinal() + 14)
    db.add(
        Invoice(
            id=1,
            customer_id=1,
            amount=250.0,
            status="issued",
            issue_date=today,
            due_date=due,
            notes="Demo invoice",
            jobs_json=json.dumps([1, 2]),
            custom_items_json=json.dumps([]),
        )
    )
    db.flush()
    db.add(
        Payment(
            invoice_id=1,
            amount=50.0,
            method="bank_transfer",
            status="Completed",
            date=nz_naive_now(),
        )
    )
    db.commit()


def _job_detail_template(
    job_id: int,
    customer_id: int,
    property_id: int,
    description: str,
    *,
    customer_name: str,
    customer_email: str,
    property_address: str,
) -> dict:
    return {
        "job_id": job_id,
        "customer_id": customer_id,
        "property_id": property_id,
        "description": description,
        "workflow_status": "Scheduled",
        "property_info": {
            "property_id": property_id,
            "address": property_address,
            "access_notes": "Side gate",
        },
        "property": {
            "property_id": property_id,
            "address": property_address,
        },
        "customer": {"id": customer_id, "name": customer_name, "email": customer_email},
        "checklist": [
            {"description": "Verify filtration system pressure", "is_completed": False},
            {"description": "Record water chemistry readings", "is_completed": False},
        ],
        "materials": [
            {"sku": "CHL-5L", "description": "Chlorine 5L", "quantity": 1},
        ],
        "attachments": [
            {
                "id": 1,
                "filename": "site_photo_front.jpg",
                "file_url": "https://example.test/files/site_photo_front.jpg",
            },
        ],
        "weather_context": {
            "summary": "Light winds; no severe weather watches.",
            "risk_level": "low",
            "forecast_url": "https://example.test/weather/mount-maunganui",
        },
    }


def seed_database_if_empty(db: Session) -> None:
    """Insert demo rows when the customers table has no rows."""
    if db.query(Customer).count() > 0:
        return

    customers_data = [
        (
            "Example Pools Ltd",
            "ops@example.test",
            "09-555-0100",
            "14 Marine Parade, Mt Maunganui",
        ),
        ("Kowhai Landscapes", "hello@kowhai.example", "03-555-0200", "22 Garden Lane, Christchurch"),
        ("Harbour Greens", "jobs@harbour.example", "04-555-0300", "5 Wharf Rd, Wellington"),
        ("Southern Turf Co", "crew@southern.example", "03-555-0400", "88 Plains Dr, Dunedin"),
        ("Urban Patch Ltd", "office@urbanpatch.example", "09-555-0500", "1 Queen St, Auckland"),
    ]
    for name, email, phone, address in customers_data:
        db.add(
            Customer(
                name=name,
                email=email,
                phone=phone,
                address=address,
                notes=None,
                tags="[]",
                is_archived=False,
            )
        )
    db.flush()

    jobs_spec = [
        (
            1,
            1,
            201,
            "Scheduled pool maintenance and chemical balance check.",
            "Example Pools Ltd",
            "ops@example.test",
            "14 Marine Parade, Mt Maunganui",
        ),
        (
            2,
            2,
            202,
            "Quarterly garden tidy and hedge trim.",
            "Kowhai Landscapes",
            "hello@kowhai.example",
            "22 Garden Lane, Christchurch",
        ),
        (
            3,
            3,
            203,
            "Irrigation system check and winter shutoff.",
            "Harbour Greens",
            "jobs@harbour.example",
            "5 Wharf Rd, Wellington",
        ),
    ]
    base_visit = nz_naive_now().replace(hour=10, minute=0, second=0, microsecond=0)
    for idx, (jid, cid, pid, desc, cname, cemail, paddr) in enumerate(jobs_spec):
        visit_dt = base_visit + timedelta(days=idx + 1)
        visit_iso = visit_dt.replace(microsecond=0).isoformat()
        detail = _job_detail_template(
            jid,
            cid,
            pid,
            desc,
            customer_name=cname,
            customer_email=cemail,
            property_address=paddr,
        )
        detail["scheduled_date"] = visit_iso
        db.add(
            Job(
                id=jid,
                customer_id=cid,
                property_id=pid,
                description=desc,
                workflow_status="Scheduled",
                scheduled_date=visit_dt,
                detail_json=json.dumps(detail),
            )
        )

    quotes_spec = [
        (1, 1, 1, "Spring lawn renewal", 500.0, 75.0, 575.0, "draft"),
        (2, 2, 1, "Hedge reduction package", 800.0, 120.0, 920.0, "draft"),
    ]
    for qid, cust_id, prop_id, title, sub, gst, total, st in quotes_spec:
        db.add(
            Quote(
                id=qid,
                customer_id=cust_id,
                property_id=prop_id,
                title=title,
                status=st,
                subtotal_ex_gst=sub,
                gst_amount=gst,
                total_inc_gst=total,
                notes=None,
                valid_until=None,
                line_items_json=json.dumps([]),
                discount_ex_gst=0.0,
            )
        )

    inv_today = nz_today()
    inv_due = date.fromordinal(inv_today.toordinal() + 14)
    db.add(
        Invoice(
            id=1,
            customer_id=1,
            amount=250.0,
            status="issued",
            issue_date=inv_today,
            due_date=inv_due,
            notes="Demo invoice",
            jobs_json=json.dumps([1, 2]),
            custom_items_json=json.dumps([]),
        )
    )
    db.flush()
    db.add(
        Payment(
            invoice_id=1,
            amount=50.0,
            method="bank_transfer",
            status="Completed",
            date=nz_naive_now(),
        )
    )

    db.commit()
