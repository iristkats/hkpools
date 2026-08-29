#!/usr/bin/env bash
# =====================================================================
# Publishes this folder as a public GitHub repo so the widget has a
# pools.json to fetch, and starts the first scrape. Run it once.
#
#     bash setup-github.sh              # repo named hkpools
#     bash setup-github.sh my-pools     # repo named my-pools
#
# It stops rather than touching a repo that already exists.
# =====================================================================
set -euo pipefail

REPO="${1:-hkpools}"
BRANCH="main"

die() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }
say() { printf '\033[36m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32mok\033[0m %s\n' "$*"; }

# ---- 1. are we in the right folder? ---------------------------------
say "Checking the folder…"
NEEDED=(scraper.py enrich.py facilities.py build_data.py status.js pools.json
        build.py parity.js .github/workflows/refresh.yml)
missing=()
for f in "${NEEDED[@]}"; do [ -f "$f" ] || missing+=("$f"); done
if [ ${#missing[@]} -gt 0 ]; then
  die "Missing: ${missing[*]}
Run this from inside the unzipped folder. If .github is the one missing,
you double-clicked the zip — Finder hides dot-folders. Unzip again with:
    unzip hkpools-source.zip -d hkpools"
fi
ok "all files present"

# ---- 2. the GitHub CLI ----------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  say "Installing the GitHub CLI…"
  if command -v brew >/dev/null 2>&1; then brew install gh
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y gh
  else
    die "Couldn't install gh automatically.
Install it from https://cli.github.com and run this script again."
  fi
fi
ok "gh $(gh --version | head -1 | awk '{print $3}')"

if ! gh auth status >/dev/null 2>&1; then
  say "Signing you in to GitHub — pick HTTPS, and 'Login with a web browser'."
  gh auth login
fi
USER=$(gh api user --jq .login)
ok "signed in as $USER"

# ---- 3. the repo ----------------------------------------------------
if gh repo view "$USER/$REPO" >/dev/null 2>&1; then
  die "$USER/$REPO already exists — stopping rather than overwriting it.
Pick another name:  bash setup-github.sh my-pools"
fi

say "Creating $USER/$REPO (public)…"
gh repo create "$REPO" --public \
  --description "LCSD swimming pool hours, refreshed twice daily" >/dev/null
ok "repo created"

# ---- 4. push --------------------------------------------------------
say "Pushing…"
[ -d .git ] || git init -q -b "$BRANCH"
git symbolic-ref -q HEAD "refs/heads/$BRANCH" >/dev/null 2>&1 \
  || git checkout -q -B "$BRANCH"

# everything except the widget file, which is pasted into Scriptable, and
# the setup script itself. index.html ships: the refresh workflow's parity
# check reads it, and GitHub Pages can serve it as the web app.
cat > .gitignore <<'EOF'
node_modules/
.DS_Store
EOF

git add -A
git -c user.name="${USER}" -c user.email="${USER}@users.noreply.github.com" \
    commit -qm "hkpools: pool data, scraper and twice-daily refresh" || true
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USER/$REPO.git"

for attempt in 1 2 3 4; do
  if git push -u origin "$BRANCH" >/dev/null 2>&1; then break; fi
  [ "$attempt" = 4 ] && die "Push failed four times — check your network and rerun."
  sleep $((2 ** attempt))
done
ok "pushed to $BRANCH"

# ---- 5. first scrape -------------------------------------------------
say "Starting the first scrape…"
sleep 3   # Actions needs a moment to register the new workflow files
if gh workflow run refresh.yml --repo "$USER/$REPO" >/dev/null 2>&1; then
  ok "scrape started — watch it at https://github.com/$USER/$REPO/actions"
else
  printf '  \033[33m--\033[0m couldn'"'"'t start it automatically. Open\n'
  printf '     https://github.com/%s/%s/actions\n' "$USER" "$REPO"
  printf '     and click "refresh pool data" -> "Run workflow".\n'
  printf '     (The committed pools.json works until then.)\n'
fi

# ---- 6. the line to paste -------------------------------------------
cat <<EOF

$(printf '\033[32mDone.\033[0m') Paste this into hkpools-widget.js in Scriptable,
replacing the DATA_URL line near the top:

  const DATA_URL = "https://raw.githubusercontent.com/$USER/$REPO/$BRANCH/pools.json";

Then follow Part 2 of WIDGET-SETUP.md.

To serve the web app too: repo Settings -> Pages -> Deploy from branch -> $BRANCH / root.
It will appear at https://$USER.github.io/$REPO/
EOF
