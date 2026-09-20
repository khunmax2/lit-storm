"""Set an account's password on the self-hosted stack.

Passwords do not survive the move from hosted Supabase: the admin API does
not return `encrypted_password`, and the hosted project's database password
is not among the app's settings. Accounts keep their id and email, so every
profile, run and audit row still points at the right person — but each one
needs its password set once on this side.

The password is typed at a prompt rather than passed as an argument, so it
does not land in shell history, in the process list, or in a terminal
someone is sharing.

    .venv/Scripts/python deploy/supabase/set_password.py            # pick from a list
    .venv/Scripts/python deploy/supabase/set_password.py admin@example.com
"""

import getpass
import pathlib
import re
import sys


def main():
    here = pathlib.Path(__file__).resolve().parent
    env_path = here / ".env"
    if not env_path.exists():
        sys.exit(f"No {env_path}. Start the stack first: docker compose up -d")
    env = dict(re.findall(r"^([A-Z_]+)=(.*)$", env_path.read_text(encoding="utf-8"), re.M))

    try:
        from supabase import create_client, ClientOptions
    except ImportError:
        sys.exit("Run this with the project's venv: .venv/Scripts/python")

    url = f"http://localhost:{env.get('SUPABASE_PORT', '8000')}"
    client = create_client(
        url,
        env["SUPABASE_SERVICE_ROLE_KEY"],
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )

    try:
        accounts = client.table("profiles").select("id,email,role").order("role").execute().data
    except Exception as error:  # noqa: BLE001 - any failure means the stack is not reachable
        sys.exit(f"Cannot reach {url}: {type(error).__name__}: {error}")
    if not accounts:
        sys.exit("No accounts in the database.")

    if len(sys.argv) > 1:
        wanted = sys.argv[1].strip().lower()
        chosen = next((a for a in accounts if (a["email"] or "").lower() == wanted), None)
        if not chosen:
            sys.exit(f"No account with email {sys.argv[1]!r}.")
    elif len(accounts) == 1:
        chosen = accounts[0]
    else:
        print("Accounts:")
        for index, account in enumerate(accounts, 1):
            print(f"  {index}. {account['email']}  ({account['role']})")
        try:
            chosen = accounts[int(input("Which one? ").strip()) - 1]
        except (ValueError, IndexError):
            sys.exit("Not one of the numbers listed.")

    print(f"Setting the password for {chosen['email']} ({chosen['role']}).")
    password = getpass.getpass("New password: ")
    if len(password) < 6:
        # GoTrue's own floor. Rejecting it here saves a round trip and an
        # error message that does not say which rule was broken.
        sys.exit("GoTrue requires at least 6 characters.")
    if password != getpass.getpass("Again: "):
        sys.exit("The two did not match. Nothing was changed.")

    try:
        client.auth.admin.update_user_by_id(chosen["id"], {"password": password})
    except Exception as error:  # noqa: BLE001 - surface whatever GoTrue said
        sys.exit(f"Failed: {type(error).__name__}: {error}")
    print(f"Done. {chosen['email']} can sign in now.")


if __name__ == "__main__":
    main()
