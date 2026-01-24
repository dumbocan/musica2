# How to Create a New GitHub Token

It seems your GitHub token might be invalid or corrupted. Please create a new token and try again.

1.  **Go to GitHub's token settings page:**
    [https://github.com/settings/tokens](https://github.com/settings/tokens)

2.  **Generate a new token:**
    *   Click "Generate new token".
    *   Select "Generate new token (classic)".
    *   Give it a descriptive name (e.g., "Gemini CLI").
    *   Set the expiration to "No expiration".
    *   Select the `repo` scope.
    *   Click "Generate token".

3.  **Copy the new token.**

4.  **Update your `.env` file:**
    *   Open your `.env` file.
    *   Find the line with `GITHUB_TOKEN` or `GH_TOKEN`.
    *   Replace the old token with the new one.

5.  **Restart the Gemini CLI:**
    *   Close this terminal.
    *   Open a new terminal.
    *   Run `source .env` in the new terminal.
    *   Start the Gemini CLI.

This should resolve the authentication issue.
