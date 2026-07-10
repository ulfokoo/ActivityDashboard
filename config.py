import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")


# ---------------------------------------------------------------------------
# Reference lists — mirrors the "Lists" sheet in the original workbook.
# These drive every dropdown in the app. Add/remove items here if you need
# to change the options, and they will update everywhere automatically.
# ---------------------------------------------------------------------------

SERVICE_AREAS = [
    "Partnership Development",
    "Concept and Project Design",
    "Proposal Development and Resource Mobilization",
    "Legal and Institutional Documentation",
    "Advisory and Consulting Services",
    "Training and Capacity Building",
    "Stakeholder Engagement",
    "Research and Assessments",
    "Field Operations",
    "Monitoring, Evaluation and Learning (MEL)",
    "Project Management Support",
    "Documentation and Reporting",
    "Meeting and Event Facilitation",
    "Other",
]

ENGAGEMENT_TYPES = [
    "Meeting",
    "Phone / Virtual Call",
    "Email Correspondence",
    "Workshop / Training",
    "Field Visit",
    "Consultation",
    "Site Assessment / Survey",
    "Conference",
    "Steering Committee",
    "Document Review",
    "Office Work / Desk Task",
    "Other",
]

STATUSES = ["Planned", "Ongoing", "Completed", "Delayed", "Cancelled", "Other"]

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Fiscal-year month order used on the Annual Dashboard (Jul -> Jun)
FISCAL_MONTHS = [
    "July", "August", "September", "October", "November", "December",
    "January", "February", "March", "April", "May", "June",
]

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

YEARS = [2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035]

WHERE_OPTIONS = [
    "Coop Bank Head Office",
    "Branch Office",
    "Partner Organization Office",
    "Government Office",
    "Field / Site Visit",
    "Virtual Meeting (Online)",
    "Conference / Event Venue",
    "Other",
]

RESPONSIBLE_ORGS = [
    "Coop Bank",
    "Government Ministry / Agency",
    "UN Agency (UNDP, UNICEF, etc.)",
    "World Bank / IFC",
    "Bilateral Donor (USAID, GIZ, DFID, etc.)",
    "Local NGO / CSO",
    "Private Sector Partner",
    "Cooperative / Union",
    "Other",
]
