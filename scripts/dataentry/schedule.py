import datetime
import json
from collections import defaultdict

import pandas as pd
import pytz

from ruamel import yaml
import ruamel

from scripts.dataentry.paths import PATH_SLIDESLIVE_OTHER


def build_plenary():
    df = pd.read_csv("downloads/schedule.csv")

    with open("downloads/keynotes.yaml") as f:
        keynotes = yaml.load(f, Loader=ruamel.yaml.Loader)

    slideslive = pd.read_csv(PATH_SLIDESLIVE_OTHER)

    author_to_presentatiod_id = {
        row["Speakers"]: row["SlidesLive link"].replace("https://slideslive.com/", "")
        for _, row in slideslive.iterrows()
    }

    keynote_map = {
        "Keynote I": "Claire Cardie",
        "Keynote II": "Rich Caruana",
        "Keynote III": "Janet Pierrehumbert",
    }

    abstract_janet = """
    To evaluate the performance of NLP systems, the standard is to use held-out test data. When the systems are deployed in real-world applications, they will only be successful if they perform well on examples that their architects never saw before. Many of these will be examples that nobody ever saw before; the central observation of generative linguistics, going back to von Humboldt, is that human language involves “The infinite use of finite means”.
    
    Predicting the real-world success of NLP systems thus comes down to predicting future human linguistic behaviour. In this talk, I will discuss some general characteristics of human linguistic behaviour, and the extent to which they are, or are not addressed in current NLP methodology. The topics I will address include: look-ahead and prediction; the role of categorization in building abstractions; effects of context; and variability across individuals.
    """.strip()

    plenary = []

    for i, row in df.iterrows():
        image = "static/images/emnlp2020/acl-logo.png"
        keynote = None
        if row["format"] != "plenary":
            continue

        event_name = row["sessionName"]
        if event_name == "Mini-break":
            continue

        if event_name.startswith("Keynote"):
            idx = event_name.split(" ")[1].count("I") - 1
            speaker = keynote_map[event_name]
            keynote = keynotes[idx]
            event_name = f"Keynote by {speaker}"
            image = f"static/images/keynotes/{'_'.join(speaker.lower().split())}.jpg"
            # presentation_id = author_to_presentatiod_id[speaker]

        start, end = get_time(row)
        assert start < end, (start, end)

        uid = "_".join(event_name.lower().split())

        sessions = [
            {"name": "P-Live Presentation", "start_time": start, "end_time": end}
        ]

        event = {
            "UID": uid,
            "title": event_name,
            "day": start.strftime("%b %d"),
            "image": image,
            "sessions": sessions,
            "rocketchat_channel": "plenary-" + "-".join([e.lower() for e in event_name.split(" ")])
        }

        if keynote:
            event["title"] = f'Keynote: {keynote["title"]}'
            if "abstract" in keynote:
                event["abstract"] = keynote["abstract"]
            elif speaker == "Janet Pierrehumbert":
                event["abstract"] = abstract_janet
            event["bio"] = keynote["bio"]
            event["presenter"] = speaker
            event["rocketchat_channel"] = "keynote-" + "-".join([x.lower() for x in speaker.split(" ")])
            # event["presentation_id"] = presentation_id

        plenary.append(event)

    with open("yamls/plenary_sessions.yml", "w") as f:
        yaml.dump(plenary, f, Dumper=ruamel.yaml.RoundTripDumper)


def build_paper_sessions():
    df = pd.read_csv("downloads/schedule.csv")

    sessions = {}
    papers_in_session = defaultdict(list)

    for _, row in df.iterrows():
        if row["format"] not in ["zoom", "gather"]:
            continue

        if row["sessionTracks"] == "Sponsor Booths":
            continue

        start, end = get_time(row)
        uid = row["sessionNumber"]
        uid = row["format"][0] + uid

        paper_id = str(row["paperID"])
        if paper_id.startswith("CL"):
            paper_id = "CL." + paper_id[2:]
        elif paper_id.startswith("TACL"):
            paper_id = "TACL." + paper_id[4:]
        elif paper_id.startswith("DEMO"):
            paper_id = "demo." + paper_id[4:]
        else:
            paper_id = "main." + paper_id

        papers_in_session[uid].append(paper_id)

        sessions[uid] = {
            "start_time": start,
            "end_time": end,
            "name": row["sessionName"],
            "long_name": row["sessionLongName"],
        }

    for uid in sessions:
        sessions[uid]["papers"] = papers_in_session[uid]

    with open("yamls/paper_sessions.yml", "w") as f:
        yaml.dump(sessions, f, Dumper=ruamel.yaml.RoundTripDumper)


def build_overall_calendar():
    df = pd.read_csv("downloads/schedule.csv")

    events = []

    for _, row in df.iterrows():
        start, end = get_time(row)

        if row["sessionTracks"] == "Sponsor Booths":
            parts = row["sessionLongName"].split(":", 1)

            day = {
                "title": f"<b>{parts[0]}</b><br>{parts[1]}",
                "start": start,
                "end": end,
                "location": "sponsors.html",
                "link": "sponsors.html",
                "category": "time",
                "calendarId": "---",
                "type": "Sponsors",
                "view": "day",
            }
            week = {
                "title": "Meet Our Sponsors In Gather.Town",
                "start": start,
                "end": end,
                "location": "sponsors.html",
                "link": "sponsors.html",
                "category": "time",
                "calendarId": "---",
                "type": "Sponsors",
                "view": "week",
            }

            events.append(day)
            events.append(week)

    class NoAliasDumper(ruamel.yaml.RoundTripDumper):
        def ignore_aliases(self, data):
            return True

    with open("yamls/overall_calendar.yml", "w") as f:
        yaml.dump(events, f, Dumper=NoAliasDumper)


def get_time(row):
    start_time = row["startUtc"]
    end_time = row["endUtc"]

    tz = pytz.UTC

    start = datetime.datetime.strptime(start_time, "%d/%m/%Y %H:%M:%S")
    end = datetime.datetime.strptime(end_time, "%d/%m/%Y %H:%M:%S")

    start = tz.localize(start)
    end = tz.localize(end)

    return start, end


if __name__ == "__main__":
    build_plenary()
    build_paper_sessions()
    build_overall_calendar()
