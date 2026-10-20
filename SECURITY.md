# Security

## Reporting a problem

If you find something here that shouldn't be public (a key, a password, an email address, an account number, a
private name, a voice or avatar ID) or a script that does something unsafe, please report it privately: open this
repository's **Security** tab and choose **Report a vulnerability**, or use the contact form at
https://giddyupdata.com/contact.html. Please don't open a public issue for these.

I'm one person. I aim to reply within a week; when I'm teaching or traveling it can take longer. There is no bug
bounty.

## In scope

- Secrets, personal details or likeness IDs committed by mistake, anywhere in the repository.

## Out of scope

- This is an example built for my own machine, not supported software. Problems other than secrets can go in an
  ordinary issue.
- Vulnerabilities in third-party tools. Please report those to their maintainers.

## If you adapt this pipeline

- Never commit keys. Keep them in a secrets manager, your operating system's keyring, environment variables or a
  file outside the repository (`AIDV_SECRETS_FILE`, see the README), and set up `.gitignore` before you create any
  `.env` file.
- The pipeline was run on a one-person machine where the agent runs with its permission prompts off. Don't copy
  that: keep the prompts on, and on a shared or company computer start from the stricter settings in the starter
  kit ([ai-workspace-blueprints](https://github.com/david-giddyupdata/ai-workspace-blueprints), `use/settings/`).
- The capture code drives a browser that you have signed in to. Anything that browser can do as you, a script can do.
- `pipeline/vendor/claude_watch.py` approves an agent's permission prompts during a recorded take. Use it only on a
  throwaway account with nothing of value in it.
- Recordings can show names, emails and account numbers. Run the privacy scan (`python -m pipeline.privacy.report`)
  and look at the frames yourself before anything is published.
