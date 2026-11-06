#!/usr/bin/env python3
"""
Helper script to push the local NIFTY 50 repository to GitHub using pure Python (Dulwich).
No Xcode command line tools or system git installation required!
"""

import sys
import os
from dulwich.repo import Repo
from dulwich.porcelain import push

REPO_PATH = os.path.dirname(os.path.abspath(__file__))


def push_repo(remote_url: str, token: str = ""):
    repo = Repo(REPO_PATH)
    
    # If token provided and URL is HTTPS, embed token
    target_url = remote_url.strip()
    if token and target_url.startswith("https://") and "@" not in target_url:
        target_url = target_url.replace("https://", f"https://{token}@")

    print(f"Pushing 'main' branch to remote: {remote_url} ...")
    try:
        # Push refs/heads/main to refs/heads/main
        push(repo, target_url, refspecs=["refs/heads/main:refs/heads/main"])
        print("✅ Successfully pushed to GitHub!")
        print("\nNext step for Streamlit.io deployment:")
        print("1. Go to https://share.streamlit.io")
        print("2. Click 'New app'")
        print(f"3. Select this repository, branch 'main', and main file 'app.py'")
        print("4. Click 'Deploy!'")
    except Exception as e:
        print(f"❌ Error pushing to GitHub: {e}")
        print("\nTips:")
        print("- Ensure the GitHub repository has been created at github.com/new")
        print("- If using a GitHub Personal Access Token (PAT), ensure it has 'repo' permission scope.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 push_to_github.py <GITHUB_REPO_URL> [GITHUB_PERSONAL_ACCESS_TOKEN]")
        print("\nExample:")
        print("  python3 push_to_github.py https://github.com/your-username/nifty50-pulse.git ghp_yourTokenHere")
        sys.exit(1)

    url = sys.argv[1]
    pat = sys.argv[2] if len(sys.argv) > 2 else ""
    push_repo(url, pat)
