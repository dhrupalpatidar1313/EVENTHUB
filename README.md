# EventHub — Event Management API

EventHub is a robust, concurrent event booking and management RESTful API built with **Django 6.1.2** and **Django REST Framework (DRF)**, powered by **PostgreSQL 17** and managed via **uv**.

---

## 📖 Table of Contents
1. [Key Features & Architecture](#key-features--architecture)
2. [Design Decision: Concurrency & Atomic Seat Allocation](#design-decision-concurrency--atomic-seat-allocation)
3. [Running the Project](#running-the-project)
   - [Option A: With Docker Compose (Recommended)](#option-a-with-docker-compose-recommended)
   - [Option B: Local Setup (without Docker)](#option-b-local-setup-without-docker)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Interactive Documentation (Swagger & Redoc)](#interactive-documentation)
6. [Business Rules Enforced](#business-rules-enforced)

---

## 🚀 Key Features & Architecture
- **Stateless JWT Authentication**: Access tokens (15 mins), rotating refresh tokens (7 days), and cryptographic token blacklisting on logout.
- **Role-Based Access Control (RBAC)**: Distinct permissions for `attendee`, `organizer`, and `admin`.
- **Atomic Booking Engine**: Eliminates overbooking races with PostgreSQL row-level locks (`select_for_update`) wrapped in `transaction.atomic()`.
- **Automated Waitlist Promotion**: First-in, first-out (FIFO) promotion when seats free up from cancellations.
- **Transaction-Safe Email Notifications**: 5 distinct lifecycle email triggers executed via `transaction.on_commit()`.
- **Comprehensive Filtering & Search**: Filter by status, venue, category, date range, seat availability, and free-text search.
- **Request Logging Middleware**: Logs method, path, status, and execution duration in milliseconds for every HTTP request.

---

## 💡 Design Decision: Concurrency & Atomic Seat Allocation

### The Challenge
When multiple users simultaneously attempt to book the final remaining seats of a popular event, a naive read-check-write flow (`if event.available_seats >= requested: event.available_seats -= requested; event.save()`) creates a race condition. Two concurrent transactions can read the same remaining seat count, pass validation simultaneously, and overcommit capacity, resulting in negative available seats.

### The Solution
All mutations affecting seat capacity reside in a dedicated, isolated service layer ([`events/services.py`](events/services.py)) using **pessimistic row-level locking**:

```python
@transaction.atomic
def reserve_seats(*, user, event_id, attendee_name, attendee_email, seats):
    # 1. Acquire row-level lock on the event. Concurrent booking transactions wait here.
    event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)

    # 2. Enforce business rules against guaranteed current state
    if seats > event.available_seats:
        fail(f"Only {event.available_seats} seat(s) available.")

    # 3. Deduct seats & persist
    event.available_seats -= seats
    event.save(update_fields=["available_seats"])

    reservation = Reservation.objects.create(...)
    transaction.on_commit(lambda: emails.reservation_confirmed(reservation.pk))
    return reservation
```

### Why this design?
1. **Zero Deadlocks**: All operations enforce strict lock ordering: **Event first, Reservation second**.
2. **Deterministic & Retry-Free**: Unlike optimistic locking (`select` + conditional `UPDATE WHERE version = x`), pessimistic locking does not fail under high contention; incoming requests simply line up briefly and execute sequentially.
3. **Database-Level Safety Net**: As a secondary line of defense, database `CheckConstraint` rules guarantee `available_seats <= total_seats` and `1 <= seats_reserved <= 5` directly in PostgreSQL.
4. **Seamless Waitlist Integration**: The same locked event row enables `promote_waitlist(event)` to evaluate and promote waiting entries immediately upon cancellation without releasing the lock.

---

## 🛠️ Running the Project

### Prerequisites
- Docker & Docker Compose **OR** Python 3.14+ with [uv](https://docs.astral.sh/uv/) installed.
- PostgreSQL 17 (if running locally without Docker).

### Option A: With Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd EVENTHUB
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env if needed (default database credentials are pre-configured)
   ```

3. **Start the application**:
   ```bash
   docker compose up --build
   ```
   This will:
   - Spin up PostgreSQL 17 with data volume persistence in `./data/postgres`.
   - Build the web image using `uv` with Python 3.14.
   - Run migrations automatically.
   - Start the development server at `http://localhost:8000`.

4. **Create an admin superuser (in a separate terminal)**:
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

---

### Option B: Local Setup (without Docker)

1. **Clone and enter directory**:
   ```bash
   git clone <repo-url>
   cd EVENTHUB
   ```

2. **Set up virtual environment using uv**:
   ```bash
   uv sync
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Ensure DB_NAME, DB_USER, DB_PASSWORD match your local PostgreSQL configuration
   ```

4. **Run migrations**:
   ```bash
   uv run python manage.py migrate
   ```

5. **Create superuser**:
   ```bash
   uv run python manage.py createsuperuser
   ```

6. **Start development server**:
   ```bash
   uv run python manage.py runserver
   ```
   The API will be available at `http://127.0.0.1:8000/`.

---

## 📚 API Endpoints Reference

All API routes are mounted under `/api/`. Protected routes require the HTTP header:
`Authorization: Bearer <access_token>`

### 1. Authentication (`/api/auth/`)
| Method | URL | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Public | Register new user (`attendee` or `organizer`). |
| `POST` | `/api/auth/login/` | Public | Login with credentials; returns JWT pair (`access`, `refresh`). |
| `POST` | `/api/auth/token/refresh/` | Public | Refresh expired access token with rotating refresh token. |
| `POST` | `/api/auth/logout/` | Authenticated | Blacklists the refresh token permanently. |
| `GET` | `/api/auth/me/` | Authenticated | Retrieve current user profile and role. |
| `PATCH` | `/api/auth/me/` | Authenticated | Update user profile info (name, address, phone, avatar). |

### 2. Categories (`/api/categories/`)
| Method | URL | Access | Description |
|---|---|---|---|
| `GET` | `/api/categories/` | Public | List all categories. |
| `GET` | `/api/categories/{id}/` | Public | Retrieve category details. |
| `POST` | `/api/categories/` | Admin | Create a category. |
| `PUT`, `PATCH` | `/api/categories/{id}/` | Admin | Update a category. |
| `DELETE` | `/api/categories/{id}/` | Admin | Delete a category (events remain with `category=null`). |

### 3. Events (`/api/events/`)
| Method | URL | Access | Description |
|---|---|---|---|
| `GET` | `/api/events/` | Public | List events with filters, search, ordering, pagination. |
| `POST` | `/api/events/` | Organizer / Admin | Create an event (organizer set automatically from token). |
| `GET` | `/api/events/{id}/` | Public | Show event details including `reservations_count`. |
| `PUT`, `PATCH` | `/api/events/{id}/` | Owner / Admin | Update event details (recalculates seats). |
| `DELETE` | `/api/events/{id}/` | Owner / Admin | Delete event (fails with 409 if reservations exist). |
| `GET` | `/api/events/mine/` | Organizer | List events created by the logged-in organizer. |
| `POST` | `/api/events/{id}/cancel/` | Owner / Admin | Cancel event, refund bookings, close waitlist, send emails. |
| `GET` | `/api/events/{id}/stats/` | Owner / Admin | Occupancy %, revenue, sold/available seats, waitlist count. |
| `GET` | `/api/events/{id}/attendees/` | Owner / Admin | List all confirmed attendees for this event. |
| `GET` | `/api/events/{id}/waitlist/` | Owner / Admin | View waiting queue in FIFO order. |
| `POST` | `/api/events/{id}/waitlist/` | Attendee / Admin | Join waitlist when seats are fully booked. |

### 4. Reservations (`/api/reservations/`)
| Method | URL | Access | Description |
|---|---|---|---|
| `GET` | `/api/reservations/` | Authenticated | List reservations (scoped by role). Filters: `?event_id=1`, `status`. |
| `POST` | `/api/reservations/` | Attendee / Admin | Atomically book 1–5 seats; returns unique `booking_code`. |
| `GET` | `/api/reservations/{id}/` | Participant | Show reservation details. |
| `POST` | `/api/reservations/{id}/cancel/` | Participant | Cancel reservation, restore seats, trigger waitlist promotion. |
| `GET` | `/api/reservations/mine/` | Authenticated | List all bookings made by the current user. |
| `GET` | `/api/reservations/lookup/?code=EH-...` | Participant | Find reservation by unique booking code. |
| `POST` | `/api/reservations/{id}/pay/` | Owner / Admin | Mock payment transition from `pending` to `paid`. |

### 5. Waitlist (`/api/waitlist/`)
| Method | URL | Access | Description |
|---|---|---|---|
| `GET` | `/api/waitlist/` | Authenticated | List current user's waitlist entries. |
| `DELETE` | `/api/waitlist/{id}/` | Owner / Admin | Leave waitlist (marks entry as `cancelled`). |

---

## 🌐 Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: [`http://localhost:8000/api/docs/`](http://localhost:8000/api/docs/)
- **Redoc UI**: [`http://localhost:8000/api/redoc/`](http://localhost:8000/api/redoc/)
- **OpenAPI 3 Schema**: [`http://localhost:8000/api/schema/`](http://localhost:8000/api/schema/)

---

## 🔒 Business Rules Enforced

| ID | Rule Description | Enforcement Layer |
|---|---|---|
| **BR-1** | 1 to 5 seats per reservation | Serializer, CheckConstraint (`reservation_seats_1_to_5`) |
| **BR-2** | Maximum 5 confirmed seats per user per event across all bookings | `services._seats_held()` |
| **BR-3** | Seats reservable only for `upcoming`/`ongoing` events with dates today or later | `services.reserve_seats()` |
| **BR-4** | Cannot reserve more than `available_seats` | `select_for_update()` capacity check |
| **BR-5** | Seat deduction and reservation creation executed atomically | `transaction.atomic()` |
| **BR-6** | Cancellation restores capacity and refunds paid reservations | `services.cancel_reservation()` |
| **BR-7** | Cannot cancel an already cancelled reservation | Validation check |
| **BR-8** | Cannot cancel past or completed events | Date & status check |
| **BR-9** | Event creation date cannot be in the past | `EventSerializer.validate_date()` |
| **BR-10** | `available_seats` defaults to `total_seats` on event creation | `EventSerializer.create()` |
| **BR-11/12** | Modifying `total_seats` recalculates `available_seats`; cannot lower below booked seats | `EventSerializer.update()` |
| **BR-13** | Events with confirmed reservations cannot be deleted (409 Conflict) | `EventViewSet.destroy()` |
| **BR-14** | Cancelling an event cascades refunds, cancels reservations, restores seats, closes waitlist | `services.cancel_event()` |
| **BR-15** | Waitlist allowed only when event capacity cannot fit requested seats | `services.join_waitlist()` |
| **BR-16/17** | FIFO waitlist promotion on cancellation; skips and cancels entries violating BR-2 | `services.promote_waitlist()` |
| **BR-18** | Mock payment transitions `pending` → `paid`; refunds on cancel | `services.pay_reservation()` |
| **BR-19** | Direct `PUT`, `PATCH`, `DELETE` disallowed on `/api/reservations/` (HTTP 405) | `http_method_names` restricted |
| **BR-20** | Unique booking code (`EH-XXXXXXXXXX`) generated upon creation | `secrets.token_hex(5)` |
