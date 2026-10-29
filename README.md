# CampusShare

A web platform where students on one campus can **lend, donate or exchange** items with each other. Built with Django as a college project.

## What it does

**Students**
- Register with a college email and verify it by email
- List items (borrow, donate or exchange) with up to 5 photos
- Browse and search with filters for category, type, condition and availability
- Request items and track them through the full lifecycle:
  Pending, Approved or Rejected, Handed over, Return initiated, Completed
  (plus Cancelled and Overdue)
- Accept or reject incoming requests, confirm returns and record the item's condition
- Rate and review each other after every completed transaction
- Get notifications for every status change, with an unread count
- Manage a profile, view other students' public profiles, and report listings or users
- See their borrowing history with filters

**Admins**
- Dashboard with live statistics
- Manage users (activate, deactivate, delete), listings (hide, remove) and categories
- Handle complaints (resolve, warn a user, or deactivate a user)
- Reports on most borrowed items, most active users, requests per month and category usage

## Tech stack

- Python and Django (SQLite database)
- Bootstrap 5 for the interface
- Git and GitHub for version control

## Project structure

| Folder | Purpose |
|---|---|
| `accounts/` | Users, registration, login, email verification, profiles |
| `resources/` | Categories, listings, browse and search |
| `borrowing/` | Requests, reviews, notifications, complaints, history |
| `adminpanel/` | Admin dashboard and management pages |
| `core/` | Home page, dashboard, base template, management commands |
| `config/` | Project settings and main URLs |

## How to run it

You need Python 3.9 or newer and Git.

```
git clone https://github.com/minumariasabu/CampusShare.git
cd CampusShare
python -m venv env
```

Activate the environment:

- Windows: `env\Scripts\activate`
- Mac/Linux: `source env/bin/activate`

Then:

```
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_campus --name "Your College" --domain yourcollege.edu.in
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000

- Students register with an email ending in the domain you set above.
- Verification and password-reset emails are printed in the terminal while no email account is configured.
- Admin pages are at `/manage/`, and Django's own admin at `/admin/`. Log in with the superuser you created.

## Overdue check

Late items are marked Overdue, and reminders are sent, by this command:

```
python manage.py check_overdue
```

Run it once a day (for example with Windows Task Scheduler or cron).

## Design documents

The project follows a written flow and page design (27 pages) and a 9-table database design.

## Known limitations

- Notifications refresh when a page loads (no live updates)
- The overdue check must be scheduled to run daily
- Single-college version
- No in-app chat between students

## Author

Minu, ABC College of Engineering