# Glow — Deployment Guide (VS Code → GitHub → Render + Vercel)

This walks you through everything, from saving the code to having a live link.

## Project structure
```
glow-store/
├── frontend/
│   ├── index.html
│   └── images/            ← drop your own product photos here later
├── backend/
│   ├── main.py
│   └── requirements.txt
├── render.yaml
└── README.md
```

---

## STEP 1 — Save the project in VS Code

1. Create a folder on your computer, e.g. `glow-store`.
2. Copy in the `frontend/` and `backend/` folders exactly as given (keep the
   same names and structure — it matters for deployment).
3. Open the folder in VS Code: `File → Open Folder → glow-store`.
4. Install the "Python" and "Live Server" extensions in VS Code (optional
   but helpful — Live Server lets you preview `index.html` instantly).

### Test locally first (recommended before deploying)
Open a terminal in VS Code (`` Ctrl+` ``):
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Leave that running. Open `frontend/index.html` in your browser (or right-click
→ "Open with Live Server"). Register an account, add items to your wishlist
and cart, and place a test order — confirm everything works before deploying.

---

## STEP 2 — Push the project to GitHub

1. In VS Code terminal, from the `glow-store` root folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Glow e-commerce site"
   ```
2. Create a `.gitignore` file in the root with:
   ```
   backend/venv/
   backend/__pycache__/
   backend/store.db
   .env
   ```
3. Create a new empty repository on GitHub (github.com → "New repository"),
   name it e.g. `glow-store`. **Don't** initialize it with a README (you
   already have one).
4. Connect and push:
   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/glow-store.git
   git branch -M main
   git push -u origin main
   ```
5. Refresh your GitHub repo page — you should see `frontend/`, `backend/`,
   and the other files there.

---

## STEP 3 — Deploy the backend on Render

1. Go to [render.com](https://render.com) and sign up / log in (you can use
   your GitHub account to sign in — this also makes connecting repos easier).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account if prompted, then select the `glow-store`
   repository.
4. Fill in the settings:
   - **Name**: `glow-backend` (this becomes part of your URL)
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
5. Under **Environment Variables**, add:
   - `SECRET_KEY` → any long random string (used to sign login tokens)
   - `FRONTEND_ORIGIN` → leave as `*` for now — you'll update this in Step 5
     once you have your Vercel URL, for better security
6. Click **Create Web Service**. Render will build and deploy — this takes
   a couple of minutes. When it's done, you'll get a URL like:
   ```
   https://glow-backend.onrender.com
   ```
7. Visit `https://glow-backend.onrender.com/health` in your browser — you
   should see `{"status":"healthy"}`. That confirms the backend is live.

**Important note on the free tier:**
- Render's free web services spin down after inactivity and take ~30–50
  seconds to wake back up on the next request — this is normal, not a bug.
- The free tier's disk is **not persistent** — if you're using the default
  SQLite database, your data (users/orders/etc.) can reset when Render
  restarts or redeploys the service. For a real production store, add a
  free Render **PostgreSQL** database (New + → PostgreSQL) and set the
  `DATABASE_URL` environment variable on your web service to the connection
  string Render gives you — the backend already supports this automatically.

---

## STEP 4 — Deploy the frontend on Vercel

1. First, open `frontend/index.html` and update this line near the top of
   the `<script>` section:
   ```js
   const API_BASE = "http://localhost:8000";
   ```
   Change it to your live Render URL from Step 3:
   ```js
   const API_BASE = "https://glow-backend.onrender.com";
   ```
   Commit and push this change:
   ```bash
   git add frontend/index.html
   git commit -m "Point frontend to deployed backend"
   git push
   ```
2. Go to [vercel.com](https://vercel.com) and sign up / log in with GitHub.
3. Click **Add New** → **Project**.
4. Import your `glow-store` repository.
5. In the configuration screen:
   - **Root Directory**: click "Edit" and select `frontend`
   - **Framework Preset**: choose "Other" (it's a static site, no build step)
   - Leave Build Command / Output Directory blank
6. Click **Deploy**. Vercel builds in seconds and gives you a URL like:
   ```
   https://glow-store.vercel.app
   ```

---

## STEP 5 — Connect the two (CORS) and finish

1. Go back to your Render backend → **Environment** tab.
2. Update `FRONTEND_ORIGIN` to your real Vercel URL:
   ```
   https://glow-store.vercel.app
   ```
3. Save — Render will redeploy automatically with the new setting.
4. Visit your Vercel link, register an account, add products to your
   wishlist/cart, and place an order to confirm everything is fully working
   end-to-end.

---

## You're live 🎉
- **Frontend**: `https://glow-store.vercel.app`
- **Backend**: `https://glow-backend.onrender.com`
- **API docs** (auto-generated): `https://glow-backend.onrender.com/docs`

## Adding your own product photos later
Drop image files into `frontend/images/` using the exact filenames listed
in `frontend/images/README.txt` (e.g. `vitamin-c-serum.jpg`), then commit
and push — Vercel redeploys automatically on every push to `main`.

## Troubleshooting
| Problem | Likely cause |
|---|---|
| Login fails with a network error | Backend still waking up (free tier) — wait ~40s and retry |
| "Couldn't sync wishlist/cart" toast | Check `API_BASE` matches your Render URL exactly, no trailing slash |
| CORS error in browser console | `FRONTEND_ORIGIN` on Render doesn't match your Vercel URL exactly |
| Orders/users disappear after a while | You're on free SQLite storage — switch to Render Postgres (see Step 3 note) |