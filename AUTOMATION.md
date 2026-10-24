# One-time setup: tested changes to automatic Streamlit deployment

The source now includes `.github/workflows/tests.yml`. It runs the Python test suite on pull requests to `main`, pushes to `main`, and manual requests. It needs no OpenAI key, paid API calls or Streamlit deployment token. It uses a read-only GitHub token, limits runs to 15 minutes and retains test reports for seven days. Browser tests are separate developer checks and are not included in this workflow.

The process is **feature branch → pull request → passing tests → merge to main → Streamlit deploys**. Streamlit watches the selected branch and does not wait for GitHub Actions on its own. Do not push an untested update directly to `main` expecting Streamlit to wait.

## 1. GitHub repository

Create a private GitHub repository named `chinese-reading-app`. Upload the extracted source contents, preserving the folder structure. `app.py` and `requirements.txt` must be at the repository root, alongside `chinese_reader/`, `assets/` and `samples/`. Do not upload the ZIP itself, `.env`, Streamlit secrets or local databases. The supplied ZIP includes source, synthetic samples and fonts, not your library.

On an iPhone, Safari's Request Desktop Website mode may make GitHub controls accessible. Uploading an entire folder tree can still be difficult. An optional writable GitHub integration or a borrowed computer can handle the initial import; not every GitHub app/integration supports writing files.

The `.github` folder can be hidden by phone file pickers. Check the repository after uploading. If `.github/workflows/tests.yml` is absent:

1. In the repository, open Actions and choose **set up a workflow yourself** (or use Code → Add file → Create new file).
2. Set the path to `.github/workflows/tests.yml`.
3. Paste the exact contents of the supplied `tests.yml` file and commit it to `main`.

This filename and indentation matter. The initial repository must use branch `main`; if yours uses another name, substitute that branch in the workflow and Streamlit settings.

## 2. Confirm Actions works

Open Actions → App tests and wait for a green **Python tests** result. If GitHub asks whether to enable Actions, enable it for your own repository. If no run appears, use Run workflow. The workflow reports the number of passing tests from the current source; it does not make a paid AI call.

A red result means do not merge the update. Open the failing step and read its error. Do not paste API keys or secrets into issues or logs. Dependency installation needs ordinary Internet access on the GitHub-hosted runner. Private repositories have plan-dependent Actions allowances; check your account's usage/billing settings before enabling paid overages.

## 3. Protect the deployment branch

After the first successful test run, open Settings → Rules → Rulesets (or Settings → Branches → branch protection, depending on GitHub's interface):

- Target `main`.
- Require a pull request before merging.
- Require the status check from this workflow, displayed as **Python tests** (it may include the workflow name).
- Require the branch to be up to date before merging.
- If available, apply the rule to administrators / disallow bypass.
- Do not require a second person's review if you are the sole maintainer.

Private-repository enforcement depends on your GitHub plan. If the required rules are unavailable, you can still follow the pull-request process manually, but untested direct pushes are not technically blocked. Do not change repository privacy merely to obtain branch rules when it contains private material.

## 4. Link Streamlit once

Sign into https://share.streamlit.io/ using GitHub. Create the app from this repository, branch `main`, entry file `app.py`, Python 3.12. Deploy after the initial tests pass. Streamlit will install `requirements.txt` and follow later commits on that branch automatically. Use the app's sharing/access controls to limit it to your family; a private repository alone does not guarantee a private deployed website.

If you want AI, put your key in Streamlit's app Secrets, not GitHub Actions:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_PINYIN_MODEL = "gpt-4.1-mini"
```

Manual mode works without these. Model access and API billing must be enabled on your OpenAI API account. The workflow has no need to read your Streamlit secrets and does not need deployment credentials.

## 5. Optional ChatGPT GitHub connection

If a GitHub integration is available in your ChatGPT Apps/Plugins settings, connect it and authorise only the intended repository where possible. Check its permissions: a read-only integration can review code but cannot create branches, push files or open pull requests. A writable coding integration or authenticated development workspace is needed for those actions. Do not paste a GitHub personal access token into chat. Account creation, login/2FA and permission approval remain your actions.

A useful instruction for future changes is: “Implement this change on a new branch, add appropriate tests and open a pull request. Keep main for tested releases.” The assistant can carry this out only when the connected tools permit those writes. Otherwise, upload the supplied updates to a new branch through GitHub's website and open the pull request yourself.

## 6. Normal update cycle

1. Back up your library through the app before a release.
2. Create an `update/...` branch and make/upload changes there.
3. Open a pull request to `main`.
4. Wait for **Python tests** to pass and review the change.
5. Merge the pull request. Streamlit detects the new `main` commit and deploys.
6. Open the app and check one story/PDF. If it fails, use Streamlit logs and revert the merge through a new tested pull request.

No manual ZIP upload to Streamlit is required after the repository is connected. The automation deploys code, not your library data. Local SQLite can disappear on Cloud restarts/redeployment: keep complete JSON backups. Durable database storage and automatic data backups are separate future work. Supabase/Postgres is not a drop-in option in the current SQLite code; migration requires implementation and testing before using it.

## Current validation

The workflow uses the same `python -m pytest -q` command already run locally. It has not run in your GitHub account until you upload it. Repository creation, branch rules, account connections and Streamlit deployment have not been performed by preparing these files.
