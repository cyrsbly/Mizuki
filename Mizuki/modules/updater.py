import asyncio
import os
import sys
import heroku3
import git
from Mizuki import telethn as borg
from Mizuki import UPSTREAM_REPO, HEROKU_APP_NAME, HEROKU_API_KEY

IS_SELECTED_DIFFERENT_BRANCH = (
    "looks like a custom branch {branch_name} "
    "is being used:\n"
    "In this case, updater is unable to identify the branch to be updated. "
    "Please check out to an official branch, and restart the updater."
)
OFFICIAL_UPSTREAM_REPO = UPSTREAM_REPO
BOT_IS_UP_TO_DATE = (
    ">> Mizuki is up-to-date <<"
)
NEW_BOT_UP_DATE_FOUND = (
    "New update found for {branch_name}\n"
    "ChangeLog: \n\n{changelog}\n"
    "Do update for Mizuki now..."
)
NEW_UP_DATE_FOUND = (
    "Alert! New Update here @ {branch_name}\n" "`Updating Mizuki...`"
)
REPO_REMOTE_NAME = "temponame"
IFFUCI_ACTIVE_BRANCH_NAME = "master"
DIFF_MARKER = "HEAD..{remote_name}/{branch_name}"
NO_HEROKU_APP_CFGD = "No heroku application found, but a key given? 😕"
HEROKU_GIT_REF_SPEC = "HEAD:refs/heads/master"
RESTARTING_APP = "`Restarting Mizuki...`"


@borg.on(events.NewMessage(pattern="^/update ?(.*)"))
async def updater(message):
    try:
        repo = git.Repo()
    except git.exc.InvalidGitRepositoryError as e:
        repo = git.Repo.init()
        origin = repo.create_remote(REPO_REMOTE_NAME, OFFICIAL_UPSTREAM_REPO)
        origin.fetch()
        repo.create_head(IFFUCI_ACTIVE_BRANCH_NAME, origin.refs.master)
        repo.heads.master.checkout(True)

    active_branch_name = repo.active_branch.name
    if active_branch_name != IFFUCI_ACTIVE_BRANCH_NAME:
        await message.edit(
            IS_SELECTED_DIFFERENT_BRANCH.format(branch_name=active_branch_name)
        )
        return False

    try:
        repo.create_remote(REPO_REMOTE_NAME, OFFICIAL_UPSTREAM_REPO)
    except Exception as e:
        print(e)

    temp_upstream_remote = repo.remote(REPO_REMOTE_NAME)
    temp_upstream_remote.fetch(active_branch_name)

    changelog = generate_change_log(
        repo,
        DIFF_MARKER.format(
            remote_name=REPO_REMOTE_NAME, branch_name=active_branch_name
        ),
    )

    if not changelog:
        await message.edit(
            "`No Update AvaiLAbLe if still you want to check just restart bot`"
        )
        return
    if message.text[8:] != "now":
        message_one = NEW_BOT_UP_DATE_FOUND.format(
            branch_name=active_branch_name, changelog=changelog
        )
        message_two = NEW_UP_DATE_FOUND.format(branch_name=active_branch_name)

        if len(message_one) > 4095:
            with open("change.log", "w+", encoding="utf8") as out_file:
                out_file.write(str(message_one))
            await tgbot.send_message(
                message.chat_id, document="change.log", caption=message_two
            )
            os.remove("change.log")
        else:
            await message.edit(message_one)
        await message.respond(f"Do `/update now` to update Mizuki.")
        return
    temp_upstream_remote.fetch(active_branch_name)
    repo.git.reset("--hard", "FETCH_HEAD")

    if Var.HEROKU_API_KEY is not None:
        import heroku3

        heroku = heroku3.from_key(HEROKU_API_KEY)
        heroku_applications = heroku.apps()
        if len(heroku_applications) >= 1:
            if HEROKU_APP_NAME is not None:
                heroku_app = None
                for i in heroku_applications:
                    if i.name == HEROKU_APP_NAME:
                        heroku_app = i
                if heroku_app is None:
                    await message.edit(
                        "Invalid APP Name. Please set the name of your bot in heroku in the var `HEROKU_APP_NAME`"
                    )
                    return
                heroku_git_url = heroku_app.git_url.replace(
                    "https://", "https://api:" + Var.HEROKU_API_KEY + "@"
                )
                if "heroku" in repo.remotes:
                    remote = repo.remote("heroku")
                    remote.set_url(heroku_git_url)
                else:
                    remote = repo.create_remote("heroku", heroku_git_url)
                asyncio.get_event_loop().create_task(
                    deploy_start(tgbot, message, HEROKU_GIT_REF_SPEC, remote)
                )

            else:
                await message.edit(
                    "Please create the var `HEROKU_APP_NAME` as the key and the name of your bot in heroku as your value."
                )
                return
        else:
            await message.edit(NO_HEROKU_APP_CFGD)
    else:
        await message.edit("No heroku api key found in `HEROKU_API_KEY` var.")


def generate_change_log(git_repo, diff_marker):
    out_put_str = ""
    d_form = "%d/%m/%y"
    for repo_change in git_repo.iter_commits(diff_marker):
        out_put_str += f"•[{repo_change.committed_datetime.strftime(d_form)}]: {repo_change.summary} <{repo_change.author}>\n"
    return out_put_str


async def deploy_start(tgbot, message, refspec, remote):
    await asyncio.sleep(2)
    await message.edit("Almost Done...")
    await message.edit(RESTARTING_APP)
    await asyncio.sleep(2)
    await message.edit(
        "Updating Mizuki...\nPlease wait for 5 minutes, modules are loading after that type `/ping` to check if I am online 👀"
    )
    await remote.push(refspec=refspec)
    await tgbot.disconnect()
    os.execl(sys.executable, sys.executable, *sys.argv)