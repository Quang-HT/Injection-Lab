# SQL Injection Training Lab

Safe web-based SQL Injection training platform built with a React + Tailwind frontend and a Flask backend. Every lab uses a simulation engine with predefined logic, mock datasets, pattern matching, and controlled responses. No raw user payload is ever executed as SQL.

## Stack

- Frontend: React + Vite + Tailwind CSS
- Backend: Python Flask
- Persistence: SQLite for user progress and captured flags only
- Training model: safe simulation engine with mock datasets and static challenge metadata

## Included Lab Tracks

- Login Bypass SQL Injection
- UNION-based SQL Injection
- Error-based SQL Injection
- Boolean-based Blind SQL Injection
- Time-based Blind SQL Injection
- Stacked Query Injection
- Second-order SQL Injection
- Filter / WAF bypass concepts
- SQL Injection Prevention and Secure Coding

Each category contains 5 levels:

1. Understand the concept
2. Recognize response behavior
3. Solve basic simulation
4. Solve advanced simulation
5. Explain or apply the secure fix

Each solved level reveals a predefined `HCSC{...}` flag and stores completion progress in SQLite.

## Safety Model

- No real exploitable SQL injection vulnerabilities are implemented.
- No raw payload is ever executed against a database.
- The backend returns mocked rows, mocked errors, mocked timing delays, and mocked query logs only.
- SQLite is used only for progress tracking with parameterized queries.
- SQL shown in the UI is educational pseudo-code or safe prepared statement examples.

## Project Structure

```text
client/
  src/
    components/
    context/
    pages/
    api.js
    App.jsx
    styles.css
server/
  app/
    data/
      challenges.py
      mock_data.py
    routes/
      api.py
    services/
      catalog.py
      simulation.py
    db.py
    config.py
  requirements.txt
  run.py
```

## Run Locally

### 1. Backend

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

The backend starts on `http://localhost:5000`.

### 2. Frontend

```bash
cd client
npm install
copy .env.example .env
npm run dev
```

The frontend starts on `http://localhost:5173`.

## Default UX

- Dark cyber lab dashboard with sidebar navigation
- Category cards and progress bars
- Terminal-style result panel
- Pseudo-SQL unsafe vs secure query comparison
- Mock dataset previews
- Flag reward panel with copy button
- Responsive lab workspace for desktop and mobile

## API Summary

- `GET /api/bootstrap`
- `GET /api/challenges/<challenge_id>`
- `POST /api/challenges/<challenge_id>/simulate`
- `POST /api/challenges/<challenge_id>/reset`

## Notes

- The current workspace environment has Python available, but Node.js is not installed here. The frontend code is complete, but `npm install` / `npm run dev` could not be executed in this environment.
- Backend verification can be done with Python tooling after Flask dependencies are installed.
