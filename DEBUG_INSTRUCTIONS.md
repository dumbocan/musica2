# GitHub Authentication Debugging Instructions

It seems there's an issue with your GitHub token configuration that is preventing the Gemini CLI from starting correctly. Please follow these steps to resolve the issue.

## Step 1: Verify your GitHub Token

1.  Go to your GitHub developer settings: [https://github.com/settings/tokens](https://github.com/settings/tokens)
2.  Make sure you have a "Personal access token (classic)" with the `repo` scope. If you don't have one, create a new one.
3.  Copy the token.

## Step 2: Configure the Gemini CLI

The Gemini CLI looks for a GitHub token in a configuration file, not in environment variables. You need to add your token to the Gemini CLI's configuration.

1.  Open a terminal and run the following command to open the Gemini CLI's settings file in a text editor:

    ```bash
    nano ~/.gemini/settings.json
    ```
    (If you prefer a different editor, replace `nano` with `vim`, `code`, etc.)

2.  The file should look something like this:

    ```json
    {
      "some_setting": "some_value"
    }
    ```

3.  You need to add a `mcp_servers` section with your GitHub token. The file should look like this:

    ```json
    {
      "some_setting": "some_value",
      "mcp_servers": {
        "github": {
          "token": "YOUR_GITHUB_TOKEN"
        }
      }
    }
    ```

    Replace `YOUR_GITHUB_TOKEN` with the token you copied from GitHub.

4.  Save the file and exit the editor.

## Step 3: Restart the Gemini CLI

Close this terminal and start a new Gemini CLI session. The error should be gone.

If you still see the error, please double-check that your token is correct and that the `settings.json` file is formatted correctly.
