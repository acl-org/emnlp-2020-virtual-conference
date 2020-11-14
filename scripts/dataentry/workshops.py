import csv
from collections import defaultdict
from dataclasses import dataclass
import random
from typing import List, Dict, Any
import re

import ruamel
from openpyxl import load_workbook
from ruamel import yaml

import numpy as np

from datetime import datetime, time, timedelta

import pandas as pd

import pytz

# https://docs.google.com/spreadsheets/d/19LRnJpae5NQd0D1NEO40kTbwDvS9f125tpsjBdevrcs/edit#gid=0
from scripts.dataentry.paths import *


@dataclass
class Session:
    name: str
    start: datetime
    end: datetime
    host: str


@dataclass
class Workshop:
    uid: str
    sessions: List[Session]
    description: str


def load_workshop_overview_excel() -> pd.DataFrame:
    wb = load_workbook(PATH_WORKSHOPS_OVERVIEW)
    ws = wb.worksheets[0]
    ws.delete_rows(1, 1)
    ws.delete_rows(27, 100)
    ws.delete_cols(7, 3)
    ws.delete_cols(8, 14)

    emnlp_workshops = pd.read_csv(PATH_WORKSHOPS_CSV)

    softconf_id_to_organizers = {
        row["softconfNumber"]: row["authors"] for _, row in emnlp_workshops.iterrows()
    }

    df = pd.DataFrame(
        ws.values,
        columns=[
            "Softconf Number",
            "UID",
            "Name",
            "Summary",
            "Authors",
            "URL",
            "Alias",
            "Old UID",
        ],
    )
    df = df.dropna(subset=["UID"])
    df["Softconf Number"] = df["Softconf Number"].fillna(-1)

    df["Softconf Number"] = df["Softconf Number"].apply(lambda x: int(x))
    df["Organizers"] = df["Softconf Number"].apply(
        lambda x: softconf_id_to_organizers[x]
    )

    return df


def build_workshops_basics() -> List[Dict[str, Any]]:
    workshops = load_workshop_overview_excel()
    schedule = load_schedule()
    zooms = get_zooms()

    data = []
    for _, row in workshops.iterrows():
        uid = row["UID"].strip()
        if uid == "WS-22":
            continue

        alias = row["Alias"]

        if alias is None:
            other = {"WS-4": "SCAI", "WS-1": "ConLL", "WS-13": "DeeLIO"}
            alias = other[row["UID"]]

        alias = alias.lower()
        sessions = [
            {
                "start_time": session.start,
                "end_time": session.end,
                "name": session.name,
                "hosts": session.host,
            }
            for session in schedule[uid].sessions
        ]

        entry = {
            "UID": uid,
            "title": row["Name"].strip(),
            "organizers": row["Organizers"].strip(),
            "abstract": row["Summary"],
            "website": row["URL"],
            "rocketchat_channel": f"workshop-{alias.lower()}",
            "alias": alias,
            "sessions": sessions,
        }

        if uid in zooms:
            entry["zoom_links"] = zooms[uid]

        data.append(entry)

    data.sort(key=lambda w: -int(w["UID"][2:]))

    return data


def load_schedule():
    wb = load_workbook(PATH_WORKSHOPS_SCHEDULE)

    data = {}
    for ws in wb.worksheets[4:]:
        workshop_id = ws["B2"].value
        assert workshop_id.startswith("WS-"), "Does not start with WS: " + workshop_id
        print(workshop_id, ws.title)

        description = ws["B3"].value or ""
        ws.delete_rows(1, 6)
        ws.delete_cols(7, 100)
        df = pd.DataFrame(
            ws.values,
            columns=[
                "Session Name",
                "Day",
                "Start Time",
                "End Time",
                "Time Zone",
                "Host",
            ],
        )
        df.dropna(subset=["Session Name"], inplace=True)

        sessions = []
        for idx, row in df.iterrows():
            name = row["Session Name"].strip()
            host = row["Host"] or "TBD"

            day = row["Day"]
            start_time = row["Start Time"]
            end_time = row["End Time"]
            tz_name = row["Time Zone"]

            if not name or not tz_name:
                continue

            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, "%H:%M").time()
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, "%H:%M").time()

            if isinstance(start_time, datetime):
                start_time = start_time.time()
            if isinstance(end_time, datetime):
                end_time = end_time.time()

            tz = pytz.timezone(tz_name)

            start = datetime.combine(day.date(), start_time)
            start = tz.localize(start)

            if start_time > end_time:
                day += timedelta(days=1)

            end = datetime.combine(day.date(), end_time)
            end = tz.localize(end)

            session = Session(name, start, end, host)
            sessions.append(session)

        workshop = Workshop(workshop_id, sessions, description)
        assert workshop_id not in data, (
            "workshop id already in data",
            workshop_id,
            data[workshop_id],
        )
        data[workshop_id] = workshop

    return data


def load_slideslive():
    # https://docs.google.com/spreadsheets/d/1Cp04DGRiDj8oY00-xDjTpjzCd_fjq3YhqOclhvFRK94/edit#gid=0
    df = pd.read_csv(PATH_SLIDESLIVE_WORKSHOPS)
    df = df.drop([0])

    workshop_df = load_workshop_overview_excel()

    fix = {
        "490": "4th Workshop on Structured Prediction for NLP",
        "510": "CoNLL 2020",
        "884": "Deep Learning Inside Out (DeeLIO): The First Workshop on Knowledge Extraction and Integration for Deep Learning Architectures",
        "1093": "SIGTYP 2020: The Second Workshop on Computational Research in Linguistic Typology",
        "1761": "Search-Oriented Conversational AI (SCAI) 2",
        "2217": "The Fourth Workshop on Online Abuse and Harms (WOAH) a.k.a. ALW",
        "2487": "1st Workshop on Computational Approaches to Discourse",
        "2575": "Workshop on Insights from Negative Results in NLP",
        "2797": "Deep Learning Inside Out (DeeLIO): The First Workshop on Knowledge Extraction and Integration for Deep Learning Architectures",
        "2800": "Deep Learning Inside Out (DeeLIO): The First Workshop on Knowledge Extraction and Integration for Deep Learning Architectures",
        "2976": "BlackboxNLP 2020: Analyzing and interpreting neural networks for NLP",
        "3476": "Interactive and Executable Semantic Parsing (Int-Ex)",
        "3561": "BlackboxNLP 2020: Analyzing and interpreting neural networks for NLP",
    }

    ws_name_to_id = {
        row["Name"]: row["UID"].strip() for _, row in workshop_df.iterrows()
    }
    corrected_venues = []
    for _, row in df.iterrows():
        venue_id = row["Organizer track name"]
        if row["Unique ID"].strip() in fix:
            correct_venue_name = fix[row["Unique ID"]]
            venue_id = ws_name_to_id[correct_venue_name]

        corrected_venues.append(venue_id)

    df["Organizer track name"] = corrected_venues

    return df


def generate_workshop_papers(slideslive: pd.DataFrame):
    venues = []
    UIDs = []
    titles = []
    authors = []
    presentation_ids = []

    for _, row in slideslive.iterrows():
        if is_not_paper(row):
            continue

        ws = row["Organizer track name"].strip()
        uid = row["Unique ID"].strip()
        venues.append(ws)
        UIDs.append(f"{ws}.{uid}")
        titles.append(row["Title"].replace("\n", " "))
        authors.append(
            "|".join(e.strip() for e in re.split(",| and | And ", row["Speakers"]))
        )
        presentation_ids.append(
            row["SlidesLive link"].replace("https://slideslive.com/", "")
        )

    data = {
        "workshop": venues,
        "UID": UIDs,
        "title": titles,
        "authors": authors,
        "presentation_id": presentation_ids,
    }

    columns = ["workshop", "UID", "title", "authors", "presentation_id"]
    df = pd.DataFrame(data, columns=columns)
    df = df.drop_duplicates(subset=["UID"])

    df.to_csv(PATH_YAMLS / "workshop_papers.csv", index=False)


def is_not_paper(row) -> bool:
    uid = row["Unique ID"].lower()
    title = row["Title"].lower()
    return (
        "invited" in uid
        or "challenge" in uid
        or "invited" in title
        or row["Unique ID"] == "Shared task"
    )


def add_invited_talks(slideslive: pd.DataFrame):
    talks_per_workshop = defaultdict(list)

    for _, row in slideslive.iterrows():
        if not is_not_paper(row):
            continue

        title = row["Title"]
        speakers = row["Speakers"]
        presentation_id = row["SlidesLive link"].replace("https://slideslive.com/", "")

        talks_per_workshop[row["Organizer track name"]].append(
            {"title": title, "speakers": speakers, "presentation_id": presentation_id}
        )

    return talks_per_workshop


def get_zooms() -> Dict[str, List[str]]:
    df = pd.read_excel(PATH_ZOOM_ACCOUNTS_WITH_PASSWORDS, sheet_name="Workshops")

    zooms = defaultdict(list)
    for _, row in df.iterrows():
        uid = row["UID"].replace(".", "-").upper()
        zooms[uid].append(row["Personal Meeting LINK"])

        for i in range(row["# of accounts"] - 1):
            zooms[uid].append(row[f"Personal Meeting LINK.{i+1}"])

    return zooms


if __name__ == "__main__":
    download_slideslive()
    download_workshops()
    download_zooms()

    # load_csv()
    data = build_workshops_basics()
    slideslive = load_slideslive()
    generate_workshop_papers(slideslive)
    talks = add_invited_talks(slideslive)

    fix_talks = slideslive[[is_not_paper(r) for _, r in slideslive.iterrows()]]
    fix_talks.to_csv(
        "yamls/fix_talks.csv",
        index=False,
        columns=["Organizer track name", "Unique ID", "Title", "Speakers"],
    )

    for ws in data:
        uid = ws["UID"]
        ws["prerecorded_talks"] = talks[uid]

    yaml.scalarstring.walk_tree(data)

    with open(PATH_YAMLS / "workshops.yml", "w") as f:
        yaml.dump(data, f, Dumper=ruamel.yaml.RoundTripDumper)
