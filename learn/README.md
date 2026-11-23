# Birthday Explorer v2: learning project

Rebuild the [Birthday Explorer](../app/README.md) (currently Streamlit) as a **FastAPI backend** with a **React + TypeScript front end**, and use it to grow as a software engineer, not only to learn new syntax.

The Streamlit app keeps working throughout. Each page is retired only once its v2 version does everything the old one did.

## Contents

1. [Why this project](#why-this-project)
2. [What each piece does](#what-each-piece-does)
3. [The target architecture](#the-target-architecture)
4. [Engineering habits to practise](#engineering-habits-to-practise)
5. [The roadmap](#the-roadmap)
6. [Python to TypeScript cheat sheet](#python-to-typescript-cheat-sheet)
7. [Running things](#running-things)
8. [Progress](#progress)

---

## Why this project

The current app works, but Streamlit does a lot for you: it builds the web server, the page layout, the widgets and the state, all from one Python script that reruns on every click. Splitting it into a backend and a front end means building those parts yourself, which is how most professional web apps are built:

| Streamlit gives you | In v2 you build | What you learn |
|---|---|---|
| One script that reruns on every click | An API that answers requests, and a page that updates only what changed | How the web works: HTTP, JSON, client and server |
| `st.selectbox` returns a value | React state (`useState`) and event handlers | How interactive UIs actually work |
| `@st.cache_data` | API caching and front-end data fetching | Where caching belongs and why |
| A page per `.py` file | Routes in FastAPI, pages and components in React | Structuring a codebase that grows |
| DataFrames passed straight to widgets | Typed API contracts (Pydantic in Python, interfaces in TypeScript) | Designing interfaces between systems |
| Nothing to test or deploy separately | Tests, CI and a deployment for each half | The habits of a professional engineer |

---

## What each piece does

| Piece | What it is | Its job here | Python equivalent |
|---|---|---|---|
| **TypeScript** | JavaScript with types | The language of the front end. Catches mistakes in the editor before code runs | Python with type hints that are enforced |
| **Node.js** | Runs JavaScript/TypeScript outside the browser | Runs the front-end dev server and tools | `python` |
| **npm** | Node's package manager | Installs React and other libraries | `pip` |
| **React** | A UI library | Builds pages out of reusable *components* (`PlayerPicker`, `GameLogTable`, `BirthdayChart`) | What Streamlit does, with full control |
| **Vite** | A build tool | Creates the React project, runs a dev server that reloads as you save | `streamlit run` |
| **FastAPI** | A Python web framework | The backend: runs the SQL queries and returns JSON | Replaces Streamlit's server |
| **Pydantic** | Data models for Python | Describes the shape of each JSON response; FastAPI validates against it | `@dataclass` with validation |
| **pytest** / **Vitest** | Test runners | Automated tests for the backend / front end | `pytest` is Python's; Vitest is the TypeScript equivalent |

---

## The target architecture

```
 Browser (localhost:5173)                     API (localhost:8000)
┌─────────────────────────────┐   HTTP    ┌──────────────────────────────┐
│ web/   React + TypeScript   │ ────────▶ │ api/   FastAPI (Python)      │
│                             │  GET      │                              │
│  pages/      Today,         │  /players │  routes/   one file per area │
│              Game logs,     │  /games   │  models/   Pydantic schemas  │
│              Player explorer│           │      │                       │
│  components/ tables, charts,│ ◀──────── │      ▼                       │
│              pickers        │   JSON    │  nba_data/  the SQL queries  │
│  api/        typed fetchers │           │  (shared with the old app)   │
└─────────────────────────────┘           └──────┬───────────────────────┘
                                                 │
                                   SQL Server, or the Parquet snapshot
```

### Proposed folders

```
nba/
├── app/            the current Streamlit app (stays until v2 replaces it)
├── nba_data/       NEW: queries.py and team stats logic, with no Streamlit imports
├── api/            NEW: FastAPI backend
│   ├── main.py
│   ├── routes/     players.py, games.py, teams.py, today.py
│   ├── schemas.py  Pydantic response models
│   └── tests/
├── web/            NEW: React + TypeScript front end (created by Vite)
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/    functions that call the API, plus generated types
│   └── package.json
├── learn/          this plan, the TypeScript lessons and the React practice app
└── src/            the data pipeline (unchanged)
```

### One key refactor

[app/queries.py](../app/queries.py) is written for Streamlit: every function has `@st.cache_data`, and the data-source check uses `@st.cache_resource`. FastAPI can't use those, so the first backend task is to **move the SQL and pandas logic into `nba_data/`**, with no Streamlit imports. Then both apps call the same functions. That's a real-world lesson in *separation of concerns*: keep the logic apart from the framework that displays it.

### Types from end to end

FastAPI describes every endpoint in an OpenAPI schema (visible at `localhost:8000/docs`). A tool called `openapi-typescript` turns that schema into TypeScript types, so the Pydantic models in Python become the interfaces in React automatically. Rename a field in Python, regenerate the types, and TypeScript underlines every place in the front end that needs updating.

---

## Engineering habits to practise

These matter more than any one library. Practise them from the first milestone, not at the end.

| Habit | What it means in this project |
|---|---|
| **Small branches, one feature each** | A branch per milestone task (`v2-players-endpoint`), merged into `main` with a pull request. Read your own diff before merging |
| **Clear commit messages** | Say *why*, not just *what*: "Move queries out of Streamlit so the API can reuse them" |
| **Write the test first, sometimes** | Every endpoint gets a pytest test. Every helper with logic (birthday phases, percentages from totals, ranks) gets a unit test |
| **Types everywhere** | Python type hints and Pydantic on the backend, strict TypeScript on the front end. No `any` |
| **Linting and formatting** | `ruff` for Python, `eslint` + `prettier` for TypeScript, so style is never a discussion |
| **Continuous integration (CI)** | GitHub Actions runs the tests and linters on every pull request |
| **Document as you go** | A README for `api/` and `web/`, written for someone who has never seen the project |
| **Measure before optimising** | Time slow endpoints before adding caching; the 1.4 s LeBron query is a good first case |
| **Ask for code review** | Ask Claude (or a person) to review each pull request, and fix what comes up |

---

## The roadmap

Each milestone has a goal, the tasks, what you'll learn and a "done when" checklist. They build on each other, so go in order.

### Milestone 0: TypeScript and React basics

Two parts, in order. React code *is* TypeScript code, so TypeScript comes first: part A is plain scripts you run with Node, and part B is React in the browser.

#### Part A: TypeScript (lessons in [typescript/](typescript/))

| Lesson | Topics |
|---|---|
| `01-basics.ts` | Variables, loops, types, interfaces, functions, `filter`/`map`/`reduce`, optional values |
| `02-types.ts` | Union types (`"Regular Season" \| "Playoffs"`), type aliases, narrowing |
| `03-functions.ts` | Arrow functions, default parameters, callbacks (functions passed to other functions, which React uses everywhere) |
| `04-async.ts` | Promises, `async`/`await`, `fetch`, JSON |
| `05-modules.ts` | `import`/`export`, splitting code across files |

**Part A is done when:** you can write a script that fetches JSON from a URL and prints a filtered, sorted summary, without looking up basic syntax.

#### Part B: React (a practice app in `react/`, created with Vite)

One small practice app that grows lesson by lesson, using hardcoded NBA data. It's a sandbox for learning, separate from the real v2 app.

| Lesson | Topics | You build |
|---|---|---|
| R1. Setup and JSX | What Vite creates, how the page starts (`main.tsx` → `App.tsx`), JSX: HTML-like code inside TypeScript, `{ }` for values | A page with a heading and today's date |
| R2. Components and props | Functions that return JSX, passing data in with props, typing props with an interface | A `PlayerCard` that shows one player |
| R3. Lists and keys | Rendering arrays with `.map()`, why each item needs a `key`, showing something only if a condition holds | A grid of `PlayerCard`s from an array |
| R4. State and events | `useState`, `onClick`, why changing a normal variable doesn't update the page | A "favourite" button on each card, and a points/rebounds/assists toggle |
| R5. Forms and lifting state | Controlled inputs (a text box whose value lives in state), moving state up to the parent so two components share it | A search box and team filter that filter the grid |
| R6. Effects and fetching | `useEffect`, loading data, loading and error states | Load the players from a JSON file instead of hardcoding them |
| R7. Styling and layout | CSS files, class names, flexbox and grid | A tidy layout: filters in a sidebar, cards in a grid |

**Part B is done when:** you can explain what React re-draws when you type in the search box, and why, and you can build a new component without copying an old one.

**How React compares to Streamlit:** Streamlit reruns your whole script on every click. React re-runs only the components whose state or props changed, and only redraws the parts of the page that differ. A lot of part B is learning to think that way.

### Milestone 1: Project setup and the first endpoint

**Tasks**
1. Create a branch `v2-setup`.
2. Move the query logic from `app/queries.py` into `nba_data/` (no Streamlit imports). Make the Streamlit app call it, wrapped in its own `@st.cache_data`, and check the app still works.
3. Create `api/` with FastAPI and one endpoint: `GET /players` (the player picker list).
4. Write a pytest test for it.
5. Open `localhost:8000/docs` and try the endpoint there.

**You'll learn:** refactoring safely, HTTP basics (methods, status codes, JSON), FastAPI routes and Pydantic models, testing an API.

**Done when:** the Streamlit app still works, `GET /players` returns JSON, and its test passes.

### Milestone 2: The first v2 components, with fake data

Now use what you learned in milestone 0 part B on the real app.

**Tasks**
1. Create `web/` with Vite (`npm create vite@latest web -- --template react-ts`).
2. Build a `PlayerPicker` component from a hardcoded list of 5 players: a search box that filters as you type.
3. Build a `GameLogTable` component from hardcoded games, in the same shape the API will return.
4. Put them on one page: picking a player shows their games.

**You'll learn:** organising a real React project (`pages/`, `components/`), designing components to be reused, matching the front end to the shape of the API's data.

**Done when:** the page works with fake data, and swapping in real data later only means changing where the data comes from.

### Milestone 3: Connect them (the Game logs page, part 1)

Game logs comes first: it's one player and one season, with clear inputs and outputs.

**Tasks**
1. Endpoints: `GET /players/{id}/seasons` and `GET /players/{id}/games?season=2025-26&season_type=Regular%20Season`.
2. Allow the front end to call the API (CORS settings in FastAPI).
3. Generate TypeScript types from the API with `openapi-typescript`.
4. Replace the fake data in `web/` with real API calls. Handle **loading** and **error** states (what happens when SQL Server is off?).
5. Add React Router so the page has its own URL: `/game-logs/2544/2025-26`.

**You'll learn:** CORS, query parameters, `useEffect` and data fetching (then TanStack Query, which handles caching and loading for you), generated types, URLs as state.

**Done when:** you can pick a player and season and see their real game log, and refreshing the browser keeps you on the same player.

### Milestone 4: Game logs page, part 2

**Tasks**
1. Column groups (box score, shooting, advanced, and so on), using the `DATASETS` idea from [game_logs.py](../app/game_logs.py).
2. Sortable table and **Download as CSV**.
3. Charts: a dot per game, the average line and a rolling average. Pick a chart library (Recharts is the easiest in React; Vega-Lite is what Altair uses under the hood, so your current charts would translate closely).
4. Averages & splits and Career tabs.
5. Unit tests for the split logic (percentages from totals, not averaged percentages).

**You'll learn:** reusable components, deriving data with `useMemo`, chart libraries, testing logic separately from the UI.

**Done when:** v2 Game logs does everything the Streamlit page does.

### Milestone 5: The Today page

**Tasks**
1. Endpoints: games on a date, birthdays within 3 days, team stats.
2. Date picker with previous / next day, kept in the URL (`/today/2026-11-23`).
3. Collapsible birthday player panels that load their data only when opened.
4. Team stats sidebar: move `league_table()` from [team_stats.py](../app/team_stats.py) into `nba_data/` and test the ranks.
5. Handle time zones (Sydney vs US dates) in one well-tested place.

**You'll learn:** dates and time zones (a classic source of bugs), lazy loading, layout with CSS, sharing components between pages.

**Done when:** v2 Today matches the Streamlit Today page.

### Milestone 6: The Player explorer page

The biggest page: filters, the birthday effect, model results and league tabs.

**Tasks**
1. Decide where filtering happens. Streamlit filters a DataFrame in pandas; in v2, should the API filter, or the browser? Write down your reasoning; it's a real design decision.
2. Endpoints for model results (`outputs/*.csv`), missed games, league leaders and pipeline status.
3. All the filters in the sidebar, kept in the URL.
4. The tabs, reusing the chart and table components from earlier milestones.

**You'll learn:** API design trade-offs, managing a lot of UI state, keeping a large page organised.

**Done when:** every Streamlit page has a v2 equivalent.

### Milestone 7: Quality and CI

(Start the simple parts of this earlier if you like.)

**Tasks**
1. `ruff` for Python, `eslint` and `prettier` for TypeScript.
2. A GitHub Actions workflow that runs both linters and both test suites on every pull request.
3. A few front-end component tests with Vitest and React Testing Library.
4. READMEs for `api/` and `web/`.

**You'll learn:** automated quality checks, CI, writing documentation for others.

**Done when:** a pull request with a failing test is blocked from merging.

### Milestone 8: Deploy it

**Tasks**
1. Run the API in Parquet mode (it already works without SQL Server, see [app/README.md](../app/README.md)).
2. Build the front end into static files (`npm run build`).
3. Deploy both. Options to compare: one container (Docker) serving both, or a static host for `web/` plus a separate API host.
4. Configure the API URL with environment variables instead of hardcoding `localhost`.
5. Retire the Streamlit app.

**You'll learn:** builds, environment configuration, Docker basics, hosting.

**Done when:** someone else can open the app from a link.

---

## Python to TypeScript cheat sheet

| Python | TypeScript |
|---|---|
| `x = 5` | `const x = 5;` (or `let x = 5;` if it will change) |
| `print(x)` | `console.log(x);` |
| `# comment` | `// comment` |
| `True` / `False` / `None` | `true` / `false` / `null` or `undefined` |
| `and` / `or` / `not` | `&&` / `\|\|` / `!` |
| `==` | `===` |
| `f"Hi {name}"` | `` `Hi ${name}` `` |
| `for x in items:` | `for (const x of items) {` |
| `if x > 3:` / `elif` / `else` | `if (x > 3) {` / `} else if {` / `} else {` |
| `len(items)` | `items.length` |
| `items.append(x)` | `items.push(x);` |
| `[x * 2 for x in items]` | `items.map((x) => x * 2)` |
| `[x for x in items if x > 3]` | `items.filter((x) => x > 3)` |
| `sum(items)` | `items.reduce((a, b) => a + b, 0)` |
| `def add(a: int, b: int) -> int:` | `function add(a: number, b: number): number {` |
| `lambda x: x * 2` | `(x) => x * 2` |
| `{"name": "LeBron"}` (dict) | `{ name: "LeBron" }` (object) |
| `@dataclass` / Pydantic model | `interface` |
| `x if x is not None else y` | `x ?? y` |
| `async def` / `await` | `async function` / `await` |
| `pip install` | `npm install` |
| `pytest` | `npx vitest` |

---

## Running things

From the `nba` folder:

```powershell
# TypeScript lessons (milestone 0, part A)
node learn/typescript/01-basics.ts

# React practice app (milestone 0, part B), once it's created in lesson R1
cd learn/react
npm run dev     # then open the link it prints, usually http://localhost:5173

# The current Streamlit app
.venv\Scripts\streamlit run app\app.py
```

Commands for the API and the React front end get added here as they're built.

Node runs `.ts` files by removing the types; it doesn't check them. So a file can run even when VS Code shows red underlines. Fix them anyway. The type-check settings are in [typescript/tsconfig.json](typescript/tsconfig.json).

---

## Progress

- [x] Install Node.js (v26)
- [ ] Milestone 0, part A: TypeScript basics
- [ ] Milestone 0, part B: React basics
- [ ] Milestone 1: Project setup and the first endpoint
- [ ] Milestone 2: The first v2 components, with fake data
- [ ] Milestone 3: Connect them (Game logs, part 1)
- [ ] Milestone 4: Game logs, part 2
- [ ] Milestone 5: The Today page
- [ ] Milestone 6: The Player explorer page
- [ ] Milestone 7: Quality and CI
- [ ] Milestone 8: Deploy it
