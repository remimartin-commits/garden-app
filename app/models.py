from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

from app.nz_time import nz_naive_now

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    notes = Column(Text)
    tags = Column(String)
    contact_details = Column(Text, nullable=True)
    billing_details = Column(Text, nullable=True)
    price_agreed_type = Column(String, nullable=True)
    price_agreed_amount = Column(Float, nullable=True)
    fuel_cost = Column(Float, nullable=False, default=10.0)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=nz_naive_now)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    property_id = Column(Integer)
    description = Column(Text)
    workflow_status = Column(String, default="Scheduled")
    assignee = Column(String, nullable=True)
    scheduled_date = Column(DateTime)
    estimated_duration_minutes = Column(Integer, nullable=True)
    hours_worked = Column(Float, nullable=True)
    created_at = Column(DateTime, default=nz_naive_now)
    detail_json = Column(Text, nullable=True)
    customer = relationship("Customer")

class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("category", "key", name="uq_app_settings_category_key"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(128), nullable=False, index=True)
    key = Column(String(128), nullable=False, index=True)
    value = Column(Text, nullable=True)


class Quote(Base):
    __tablename__ = "quotes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    property_id = Column(Integer, nullable=False, default=1)
    title = Column(String, nullable=False, default="")
    status = Column(String, default="draft")
    agreed_price = Column(Float, nullable=True)
    subtotal_ex_gst = Column(Float, nullable=True)
    gst_amount = Column(Float, nullable=True)
    total_inc_gst = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    valid_until = Column(String, nullable=True)
    created_at = Column(DateTime, default=nz_naive_now)
    line_items_json = Column(Text, nullable=True)
    discount_ex_gst = Column(Float, nullable=True)
    customer = relationship("Customer")


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="issued")
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    jobs_json = Column(Text, nullable=True)
    custom_items_json = Column(Text, nullable=True)
    customer = relationship("Customer")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, default="bank_transfer")
    status = Column(String, default="Completed")
    date = Column(DateTime, default=nz_naive_now)
