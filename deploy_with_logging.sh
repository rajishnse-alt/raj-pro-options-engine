#!/bin/bash
# Quick deployment script with logging setup
# Usage: bash deploy_with_logging.sh "message"

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT_MSG="${1:-Add logging system and auto-commit debug logs}"

echo "🚀 Deploying Raj Pro Options Engine with logging..."
echo ""

# Change to repo directory
cd "$REPO_DIR"

# Ensure we're in a git repo
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository. Initializing..."
    git init
fi

# Configure git (if not already set)
if [ -z "$(git config user.name)" ]; then
    echo "📝 Configuring git user..."
    git config user.name "Raj Options Engine"
    git config user.email "rajish.g.nair@gmail.com"
fi

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs

# Create .gitignore entry for logs (keep logs in repo for GitHub)
if [ ! -f ".gitignore" ]; then
    echo ".env" > .gitignore
    echo "__pycache__/" >> .gitignore
    echo "*.pyc" >> .gitignore
    echo ".streamlit/secrets.toml" >> .gitignore
fi

# Add files
echo "📦 Adding files..."
git add -A

# Commit
echo "💾 Committing changes..."
git commit -m "$COMMIT_MSG" || echo "No changes to commit"

# Push
echo "🔄 Pushing to GitHub..."
git push origin main 2>/dev/null || git push origin main -u || echo "⚠️ Could not push (no upstream?)"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Refresh your Streamlit Cloud app"
echo "2. View logs: python log_viewer.py latest"
echo "3. Check GitHub: logs/ folder"
echo ""
