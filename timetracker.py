import time

import click
import pendulum
import requests
from requests.auth import HTTPBasicAuth
from toolz import groupby, valmap


def get_entries(token, workspace_id, start, end, client_id=None):
    start_date = start.set(hour=0, minute=0, second=0, microsecond=0)
    end_date = end.set(hour=0, minute=0, second=0, microsecond=0)
    page = 1
    while True:
        params = {
            "user_agent": "Thinking Machines",
            "workspace_id": workspace_id,
            "since": start_date.isoformat(),
            "until": end_date.isoformat(),
            "page": page,
        }
        if client_id:
            params["client_ids"] = client_id
        resp = requests.get(
            "https://api.track.toggl.com/reports/api/v2/details",
            params=params,
            auth=HTTPBasicAuth(token, "api_token"),
        ).json()
        for entry in resp.get("data", []):
            yield entry
        page += 1
        per_page = resp["per_page"]
        total_count = resp["total_count"]
        if page * per_page >= total_count:
            break


def summarize(entries, timezone):
    mod_entries = [
        {
            "date": pendulum.parse(e["start"])
            .in_timezone(timezone)
            .format("YYYY-MM-DD"),
            **e,
        }
        for e in entries
    ]
    summary = valmap(
        lambda e: sum(map(lambda i: i["dur"], e)),
        groupby(
            key=lambda x: (x["date"], x.get("project"), x.get("description")),
            seq=mod_entries,
        ),
    )
    formated_summaries = [
        {
            "date": k[0],
            "project": k[1],
            "description": k[2],
            "duration": v,
        }
        for k, v in summary.items()
    ]
    return groupby("date", formated_summaries)


def format_report(date, summary):
    r = f"checkin {date}\n"
    for entry in summary:
        project = entry["project"] if entry["project"] else "no-project"
        description = entry["description"]
        duration_hrs = entry["duration"] / 60 / 60 / 1000
        if duration_hrs < 0:
            print(
                f"WARN: Got negative time for {description}. There might be a running timer"
            )
        r += f"- {duration_hrs:.2f} {'hrs' if duration_hrs>1.0 else 'hr'} #{project.lower()} {description}\n"
    return r


def submit_checkins(token, channel, checkins):
    for report in checkins:
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "channel": channel,
                "text": report,
                "as_user": True,
                "link_names": True,
            },
        )
        time.sleep(1.0)


@click.command()
@click.option("--since", type=str)
@click.option("--until", type=str)
@click.option("--toggl-token", type=str)
@click.option("--toggl-workspace-id", type=str)
@click.option("--toggl-client-id", type=str)
@click.option("--slack-token", type=str)
@click.option("--slack-channel", type=str, default="#dailycheckin")
@click.option("--timezone", type=str, default="Asia/Manila")
def main(
    since,
    until,
    toggl_token,
    toggl_workspace_id,
    toggl_client_id,
    slack_token,
    slack_channel,
    timezone,
):
    if toggl_token is None or toggl_token == "":
        raise ValueError("Toggl token is needed")
    if toggl_workspace_id is None or toggl_workspace_id == "":
        raise ValueError("Toggl workspace id is needed")
    now = pendulum.now(timezone)
    if since:
        start = pendulum.parse(since).set(tz=timezone)
    else:
        start = now
    if until:
        end = pendulum.parse(until).set(tz=timezone)
    else:
        end = now
    entries = get_entries(
        toggl_token, toggl_workspace_id, start, end, client_id=toggl_client_id
    )
    summaries = summarize(entries, timezone)
    checkins = []
    for date, summary in summaries.items():
        report = format_report(date, summary)
        checkins.append(report)
        print(report)
    if (
        checkins
        and slack_token
        and slack_channel
        and click.confirm(f"Submit to {slack_channel}?")
    ):
        submit_checkins(slack_token, slack_channel, checkins)


if "__main__" == __name__:
    main(auto_envvar_prefix="TIMETRACKER")
