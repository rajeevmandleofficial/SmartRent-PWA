# ⚡ SmartRent — Progressive Web Application (PWA)

> Production-ready, mobile-first Property, Tenant & Sub-meter Billing Management System built with **Django 5.x + PostgreSQL + TailwindCSS + HTMX + Alpine.js**.

---

## 🌟 Key Features

1. **Landlord Authentication & Multi-Tenancy**:
   - Clean register/login flow. Every landlord strictly manages only their own flats and tenants.
2. **Module 1: Flat & Room Registry**:
   - 1-click room creation, base rents, default maintenance, sub-meter rates, and live occupancy status (`Bhara hua` vs `Khali`).
3. **Module 2: Tenant Profile & 1-Click Document Vault**:
   - Tenant onboarding with 10-digit mobile validation.
   - **Document Vault**: Secure uploads for Aadhaar Card and Rent Agreement (PDF/Images) with 1-click preview and download.
   - 1-click **Vacate Tenant** action that auto-syncs the room to Vacant (`Khali`).
4. **Module 3: Sub-Meter Electricity Calculator & Auto-Bill**:
   - Landlord selects Room $\rightarrow$ App auto-fills Base Rent, Maintenance, Previous Meter Reading, and Active Tenant.
   - Landlord types Current Reading $\rightarrow$ Alpine.js dynamically live-calculates:
     $$\text{Units Consumed} = \text{Current Reading} - \text{Previous Reading}$$
     $$\text{Electricity Bill} = \text{Units Consumed} \times \text{Rate Per Unit}$$
     $$\text{Total Monthly Bill} = \text{Rent} + \text{Electricity} + \text{Maintenance}$$
   - Auto-updates `Room.current_meter_reading` for next month's billing cycle!
5. **Module 4: WhatsApp Reminders, 1-Click HTMX Status & PDF Receipts**:
   - Pre-formatted WhatsApp deep links: `https://wa.me/91<mobile>?text=...` with polite, itemized bill breakdown.
   - 1-Click HTMX Status Toggle (flips between `Pending` and `Paid` without page reload).
   - Downloadable Digital PDF rent receipts powered by `xhtml2pdf`.
6. **Mobile-First PWA**:
   - `manifest.json`, `service-worker.js` with offline caching, mobile bottom navigation bar.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.14 / 3.11+, Django 5.x / 6.x
- **Database**: PostgreSQL 18 (`psycopg2-binary`, `python-decouple`)
- **Frontend**: Django Templates + TailwindCSS CDN + HTMX 1.9 + Alpine.js 3.13
- **PDF Engine**: `xhtml2pdf` + `reportlab`
- **PWA**: Web App Manifest & Service Worker

---

## ⚡ Quick Start

### 1. Environment & Dependencies
```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Install requirements (already installed in venv)
pip install -r requirements.txt
```

### 2. Configure `.env`
Ensure your PostgreSQL credentials in `.env` are set:
```ini
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*
DB_ENGINE=postgresql
DB_NAME=smartrent_db
DB_USER=postgres
DB_PASSWORD=root
DB_HOST=localhost
DB_PORT=5432
```

### 3. Run Migrations & Start Server
```powershell
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 4. Demo Login Credentials
- **URL**: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- **Username**: `rajesh_landlord`
- **Password**: `pass1234`
