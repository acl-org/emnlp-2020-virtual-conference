import copy
import csv
import glob
import itertools
import json
import os
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta
from itertools import chain
from typing import Any, DefaultDict, Dict, List, Tuple

import jsons
import pytz
import yaml

from miniconf.site_data import (
    CommitteeMember,
    Paper,
    PaperContent,
    PlenarySession,
    PlenaryVideo,
    SessionInfo,
    SocialEvent,
    SocialEventOrganizers,
    Tutorial,
    TutorialSessionInfo,
    Workshop,
    WorkshopPaper,
)


def load_site_data(
    site_data_path: str,
    site_data: Dict[str, Any],
    by_uid: Dict[str, Any],
    qa_session_length_hr: int,
) -> List[str]:
    """Loads all site data at once.

    Populates the `committee` and `by_uid` using files under `site_data_path`.

    NOTE: site_data[filename][field]
    """
    registered_sitedata = {
        "config",
        # index.html
        "committee",
        # schedule.html
        "overall_calendar",
        "plenary_sessions",
        "business_meeting",
        "review_meeting",
        # tutorials.html
        "tutorials",
        # papers.html
        "main_papers",
        "demo_papers",
        "srw_papers",
        "cl_papers",
        "tacl_papers",
        "paper_recs",
        "papers_projection",
        "main_paper_sessions",
        "demo_paper_sessions",
        "srw_paper_sessions",
        "cl_paper_sessions",
        "tacl_paper_sessions",
        "main_paper_zoom_links",
        "demo_paper_zoom_links",
        "srw_paper_zoom_links",
        "cl_paper_zoom_links",
        "tacl_paper_zoom_links",
        "main_paper_slideslive_ids",
        "demo_paper_slideslive_ids",
        "srw_paper_slideslive_ids",
        "cl_paper_slideslive_ids",
        "tacl_paper_slideslive_ids",
        # socials.html
        "socials",
        # workshops.html
        "workshops",
        "w1_papers",
        "w2_papers",
        "w3_papers",
        "w4_papers",
        "w5_papers",
        "w6_papers",
        "w7_papers",
        "w8_papers",
        "w9_papers",
        "w10_papers",
        "w11_papers",
        "w12_papers",
        "w13_papers",
        "w14_papers",
        "w15_papers",
        "w16_papers",
        "w17_papers",
        "w18_papers",
        "w19_papers",
        "w20_papers",
        "workshop_schedules",
        # sponsors.html
        "sponsors",
        # about.html
        "code_of_conduct",
        "faq",
    }
    extra_files = []
    # Load all for your sitedata one time.
    for f in glob.glob(site_data_path + "/*"):
        filename = os.path.basename(f)
        if filename == "inbox":
            continue
        name, typ = filename.split(".")
        if name not in registered_sitedata:
            continue

        extra_files.append(f)
        if typ == "json":
            site_data[name] = json.load(open(f))
        elif typ in {"csv", "tsv"}:
            site_data[name] = list(csv.DictReader(open(f)))
        elif typ == "yml":
            site_data[name] = yaml.load(open(f).read(), Loader=yaml.SafeLoader)
    assert set(site_data.keys()) == registered_sitedata, registered_sitedata - set(
        site_data.keys()
    )

    display_time_format = "%H:%M"

    # index.html
    site_data["committee"] = build_committee(site_data["committee"]["committee"])

    # schedule.html
    generate_tutorial_events(site_data)
    generate_workshop_events(site_data)
    site_data["calendar"] = build_schedule(site_data["overall_calendar"])

    # plenary_sessions.html
    plenary_sessions = build_plenary_sessions(
        raw_plenary_sessions=site_data["plenary_sessions"],
        raw_plenary_videos={
            "business_meeting": site_data["business_meeting"],
            "review_meeting": site_data["review_meeting"],
        },
    )

    site_data["plenary_sessions"] = plenary_sessions
    by_uid["plenary_sessions"] = {
        plenary_session.id: plenary_session
        for _, plenary_sessions_on_date in plenary_sessions.items()
        for plenary_session in plenary_sessions_on_date
    }
    site_data["plenary_session_days"] = [
        [day.replace(" ", "").lower(), day, ""] for day in plenary_sessions
    ]
    site_data["plenary_session_days"][0][-1] = "active"

    # papers.{html,json}
    papers = build_papers(
        raw_papers=site_data["main_papers"]
        + site_data["demo_papers"]
        + site_data["srw_papers"]
        + site_data["cl_papers"]
        + site_data["tacl_papers"],
        all_paper_sessions=[
            site_data["main_paper_sessions"],
            site_data["demo_paper_sessions"],
            site_data["srw_paper_sessions"],
            site_data["cl_paper_sessions"],
            site_data["tacl_paper_sessions"],
        ],
        qa_session_length_hr=qa_session_length_hr,
        all_paper_zoom_links=site_data["main_paper_zoom_links"]
        + site_data["demo_paper_zoom_links"]
        + site_data["srw_paper_zoom_links"]
        + site_data["cl_paper_zoom_links"]
        + site_data["tacl_paper_zoom_links"],
        all_paper_slideslive_ids=site_data["main_paper_slideslive_ids"]
        + site_data["demo_paper_slideslive_ids"]
        + site_data["srw_paper_slideslive_ids"]
        + site_data["cl_paper_slideslive_ids"]
        + site_data["tacl_paper_slideslive_ids"],
        paper_recs=site_data["paper_recs"],
        paper_images_path=site_data["config"]["paper_images_path"],
    )
    for prefix in ["main", "demo", "srw", "cl", "tacl"]:
        for suffix in [
            "papers",
            "paper_sessions",
            "paper_zoom_links",
            "paper_slideslive_ids",
        ]:
            del site_data[f"{prefix}_{suffix}"]
    site_data["papers"] = papers
    demo_and_srw_tracks = ["System Demonstrations", "Student Research Workshop"]
    site_data["tracks"] = list(
        sorted(
            [
                track
                for track in {paper.content.track for paper in papers}
                if track not in demo_and_srw_tracks
            ]
        )
    )
    site_data["tracks"] += demo_and_srw_tracks
    # paper_<uid>.html
    by_uid["papers"] = {paper.id: paper for paper in papers}

    # serve_papers_projection.json
    all_paper_ids_with_projection = {
        item["id"] for item in site_data["papers_projection"]
    }
    for paper_id in set(by_uid["papers"].keys()) - all_paper_ids_with_projection:
        print(f"WARNING: {paper_id} does not have a projection")

    # tutorials.html
    tutorials = build_tutorials(site_data["tutorials"])
    site_data["tutorials"] = tutorials
    site_data["tutorial_calendar"] = build_tutorial_schedule(
        site_data["overall_calendar"]
    )
    # tutorial_<uid>.html
    by_uid["tutorials"] = {tutorial.id: tutorial for tutorial in tutorials}

    # workshops.html
    workshops = build_workshops(
        raw_workshops=site_data["workshops"],
        raw_workshop_papers={
            "W1": site_data["w1_papers"],
            "W2": site_data["w2_papers"],
            "W3": site_data["w3_papers"],
            "W4": site_data["w4_papers"],
            "W5": site_data["w5_papers"],
            "W6": site_data["w6_papers"],
            "W7": site_data["w7_papers"],
            "W8": site_data["w8_papers"],
            "W9": site_data["w9_papers"],
            "W10": site_data["w10_papers"],
            "W11": site_data["w11_papers"],
            "W12": site_data["w12_papers"],
            "W13": site_data["w13_papers"],
            "W14": site_data["w14_papers"],
            "W15": site_data["w15_papers"],
            "W16": site_data["w16_papers"],
            "W17": site_data["w17_papers"],
            "W18": site_data["w18_papers"],
            "W19": site_data["w19_papers"],
            "W20": site_data["w20_papers"],
        },
        workshop_schedules=site_data["workshop_schedules"],
    )
    site_data["workshops"] = workshops
    # workshop_<uid>.html
    by_uid["workshops"] = {workshop.id: workshop for workshop in workshops}

    # socials.html
    social_events = build_socials(site_data["socials"])
    site_data["socials"] = social_events

    # sponsors.html
    build_sponsors(site_data, by_uid, display_time_format)

    # about.html
    site_data["faq"] = site_data["faq"]["FAQ"]
    site_data["code_of_conduct"] = site_data["code_of_conduct"]["CodeOfConduct"]

    print("Data Successfully Loaded")
    return extra_files


def extract_list_field(v, key):
    value = v.get(key, "")
    if isinstance(value, list):
        return value
    else:
        return value.split("|")


def build_committee(
    raw_committee: List[Dict[str, Any]]
) -> Dict[str, List[CommitteeMember]]:
    # We want to show the committee grouped by role. Grouping has to be done in python since jinja's groupby sorts
    # groups by name, i.e. the general chair would not be on top anymore because it doesn't start with A.
    # See https://github.com/pallets/jinja/issues/250

    committee = [jsons.load(item, cls=CommitteeMember) for item in raw_committee]
    committee_by_role = OrderedDict()
    for role, members in itertools.groupby(committee, lambda member: member.role):
        member_list = list(members)
        # add plural 's' to "chair" roles with multiple members
        if role.lower().endswith("chair") and len(member_list) > 1:
            role += "s"
        committee_by_role[role] = member_list

    return committee_by_role


def build_plenary_sessions(
    raw_plenary_sessions: List[Dict[str, Any]],
    raw_plenary_videos: Dict[str, List[Dict[str, Any]]],
) -> DefaultDict[str, List[PlenarySession]]:

    plenary_videos: DefaultDict[str, List[PlenaryVideo]] = defaultdict(list)
    for plenary_id, videos in raw_plenary_videos.items():
        for item in videos:
            plenary_videos[plenary_id].append(
                PlenaryVideo(
                    id=item["UID"],
                    title=item["title"],
                    speakers=item["speakers"],
                    presentation_id=item["presentation_id"],
                )
            )

    plenary_sessions: DefaultDict[str, List[PlenarySession]] = defaultdict(list)
    for item in raw_plenary_sessions:
        plenary_sessions[item["day"]].append(
            PlenarySession(
                id=item["UID"],
                title=item["title"],
                image=item["image"],
                day=item["day"],
                sessions=[
                    SessionInfo(
                        session_name=session.get("name"),
                        start_time=session.get("start_time"),
                        end_time=session.get("end_time"),
                        zoom_link=session.get("zoom_link"),
                    )
                    for session in item.get("sessions")
                ],
                presenter=item.get("presenter"),
                institution=item.get("institution"),
                abstract=item.get("abstract"),
                bio=item.get("bio"),
                presentation_id=item.get("presentation_id"),
                rocketchat_channel=item.get("rocketchat_channel"),
                videos=plenary_videos[item["UID"]]
                if item["UID"] in ["business_meeting", "review_meeting"]
                else None,
            )
        )
    return plenary_sessions


def generate_tutorial_events(site_data: Dict[str, Any]):
    """ We add sessions from tutorials and compute the overall tutorial blocks for the weekly view. """

    # Add tutorial sessions to calendar
    sessions_by_day: Dict[date, List[Tuple[datetime, datetime]]] = defaultdict(list)
    for tutorial in site_data["tutorials"]:
        uid = tutorial["UID"]
        for session in tutorial["sessions"]:
            start = session["start_time"]
            end = session["end_time"]
            event = {
                "title": f"{uid}: {tutorial['title']}<br/> <br/> <i>{tutorial['organizers']}</i>",
                "start": start,
                "end": end,
                "location": f"tutorial_{uid}.html",
                "link": f"tutorial_{uid}.html",
                "category": "time",
                "calendarId": "---",
                "type": "Tutorials",
                "view": "day",
            }
            site_data["overall_calendar"].append(event)

            start_day = start.date()
            end_day = end.date()

            assert start_day == end_day, "Tutorial session spans more than a day"
            assert start < end, "Session start after session end"

            sessions_by_day[start_day].append((start, end))

    # Compute start and end of tutorial blocks
    for tutorial_day in sessions_by_day:
        min_start = min([t[0] for t in sessions_by_day[tutorial_day]])
        max_end = max([t[1] for t in sessions_by_day[tutorial_day]])

        event = {
            "title": "Tutorials",
            "start": min_start,
            "end": max_end,
            "location": "tutorials.html",
            "link": "tutorials.html",
            "category": "time",
            "calendarId": "---",
            "type": "Tutorials",
            "view": "week",
        }
        site_data["overall_calendar"].append(event)


def generate_workshop_events(site_data: Dict[str, Any]):
    """ We add sessions from workshops and compute the overall workshops blocks for the weekly view. """
    # Add workshop sessions to calendar
    sessions_by_day: Dict[date, List[Tuple[datetime, datetime]]] = defaultdict(list)

    for workshop in site_data["workshops"]:
        uid = workshop["UID"]
        for session in workshop["sessions"]:
            start = session["start_time"]
            end = session["end_time"]

            event = {
                "title": f"{workshop['title']}<br/> <br/> <i>{', '.join(workshop['organizers'])}</i>",
                "start": start,
                "end": end,
                "location": f"workshop_{uid}.html",
                "link": f"workshop_{uid}.html",
                "category": "time",
                "calendarId": "---",
                "type": "Workshops",
                "view": "day",
            }
            site_data["overall_calendar"].append(event)

            start_day = start.date()
            end_day = end.date()

            assert start_day == end_day, "Tutorial session spans more than a day"
            assert start < end, "Session start after session end"

            sessions_by_day[start_day].append((start, end))

    # Compute start and end of workshop blocks
    for workshop_day in sessions_by_day:
        min_start = min([t[0] for t in sessions_by_day[workshop_day]])
        max_end = max([t[1] for t in sessions_by_day[workshop_day]])

        event = {
            "title": "Workshops",
            "start": min_start,
            "end": max_end,
            "location": "workshops.html",
            "link": "workshops.html",
            "category": "time",
            "calendarId": "---",
            "type": "Workshops",
            "view": "week",
        }
        site_data["overall_calendar"].append(event)


def build_schedule(overall_calendar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    events = [
        copy.deepcopy(event)
        for event in overall_calendar
        if event["type"]
        in {"Plenary Sessions", "Tutorials", "Workshops", "QA Sessions", "Socials"}
    ]

    for event in events:
        event_type = event["type"]
        if event_type == "Plenary Sessions":
            event["classNames"] = ["calendar-event-plenary"]
            event["url"] = event["link"]
        elif event_type == "Tutorials":
            event["classNames"] = ["calendar-event-tutorial"]
            event["url"] = event["link"]
        elif event_type == "Workshops":
            event["classNames"] = ["calendar-event-workshops"]
            event["url"] = event["link"]
        elif event_type == "QA Sessions":
            event["classNames"] = ["calendar-event-qa"]
            event["url"] = event["link"]
        elif event_type == "Socials":
            event["classNames"] = ["calendar-event-socials"]
            event["url"] = event["link"]
        else:
            event["classNames"] = ["calendar-event-other"]
            event["url"] = event["link"]

        event["classNames"].append("calendar-event")
    return events


def build_tutorial_schedule(
    overall_calendar: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    events = [
        copy.deepcopy(event)
        for event in overall_calendar
        if event["type"] in {"Tutorials"}
    ]

    for event in events:
        event["classNames"] = ["calendar-event-tutorial"]
        event["url"] = event["link"]
        event["classNames"].append("calendar-event")
    return events


def normalize_track_name(track_name: str) -> str:
    if track_name == "SRW":
        return "Student Research Workshop"
    elif track_name == "Demo":
        return "System Demonstrations"
    return track_name


def get_card_image_path_for_paper(paper_id: str, paper_images_path: str) -> str:
    return f"{paper_images_path}/{paper_id}.png"


def build_papers(
    raw_papers: List[Dict[str, str]],
    all_paper_sessions: List[Dict[str, Dict[str, Any]]],
    qa_session_length_hr: int,
    all_paper_zoom_links: List[Dict[str, str]],
    all_paper_slideslive_ids: List[Dict[str, str]],
    paper_recs: Dict[str, List[str]],
    paper_images_path: str,
) -> List[Paper]:
    """Builds the site_data["papers"].

    Each entry in the papers has the following fields:
    - UID: str
    - title: str
    - authors: str (separated by '|')
    - keywords: str (separated by '|')
    - track: str
    - paper_type: str (i.e., "Long", "Short", "SRW", "Demo")
    - pdf_url: str
    - demo_url: str

    The paper_schedule file contains the live QA session slots for each paper.
    An example paper_sessions.yml file is shown below.
    ```yaml
    1A:
      date: 2020-07-06_05:00:00
      papers:
      - main.1
      - main.2
    2A:
      date: 2020-07-06_08:00:00
      papers:
      - main.17
      - main.19
    ```
    """
    # build the lookup from (paper, slot) to zoom_link
    zoom_info_for_paper_session: Dict[str, Dict[str, str]] = {}
    for item in all_paper_zoom_links:
        paper_id = item["UID"]
        session_name = item["session_name"]
        paper_session_id = f"{paper_id}-{session_name}"
        assert paper_session_id not in zoom_info_for_paper_session
        zoom_info_for_paper_session[paper_session_id] = item

    # build the lookup from paper to slideslive presentation ID
    presentation_id_for_paper: Dict[str, str] = {}
    for item in all_paper_slideslive_ids:
        paper_id = item["UID"]
        presentation_id = item["presentation_id"]
        assert paper_id not in presentation_id_for_paper
        presentation_id_for_paper[paper_id] = presentation_id

    # build the lookup from paper to slots
    sessions_for_paper: DefaultDict[str, List[SessionInfo]] = defaultdict(list)
    for session_name, session_info in chain(
        *[paper_sessions.items() for paper_sessions in all_paper_sessions]
    ):
        session_date = session_info["date"]
        start_time = datetime.strptime(session_date, "%Y-%m-%d_%H:%M:%S")
        end_time = start_time + timedelta(hours=qa_session_length_hr)
        for paper_id in session_info["papers"]:
            paper_session_id = f"{paper_id}-{session_name}"
            zoom_info = zoom_info_for_paper_session[paper_session_id]
            assert (
                datetime.strptime(zoom_info["starttime"], "%Y-%m-%dT%H:%M:%SZ")
                == start_time
            ), paper_id
            sessions_for_paper[paper_id].append(
                SessionInfo(
                    session_name=session_name,
                    start_time=start_time,
                    end_time=end_time,
                    zoom_link=zoom_info["zoom_join_link"],
                )
            )

    papers = [
        Paper(
            id=item["UID"],
            forum=item["UID"],
            card_image_path=get_card_image_path_for_paper(
                item["UID"], paper_images_path
            ),
            presentation_id=presentation_id_for_paper.get(item["UID"]),
            content=PaperContent(
                title=item["title"],
                authors=extract_list_field(item, "authors"),
                keywords=extract_list_field(item, "keywords"),
                abstract=item["abstract"],
                tldr=item["abstract"][:250] + "...",
                pdf_url=item.get("pdf_url", ""),
                demo_url=item.get("demo_url", ""),
                track=normalize_track_name(item.get("track", "")),
                paper_type=item.get("paper_type", ""),
                sessions=sessions_for_paper[item["UID"]],
                similar_paper_uids=paper_recs.get(item["UID"], [item["UID"]]),
            ),
        )
        for item in raw_papers
    ]

    # throw warnings for missing information
    for paper in papers:
        if not paper.presentation_id:
            print(f"WARNING: presentation_id not set for {paper.id}")
        if not paper.content.track:
            print(f"WARNING: track not set for {paper.id}")
        if len(paper.content.sessions) != 2:
            print(
                f"WARNING: found {len(paper.content.sessions)} sessions for {paper.id}"
            )
        if not paper.content.similar_paper_uids:
            print(f"WARNING: empty similar_paper_uids for {paper.id}")

    return papers


def parse_session_time(session_time_str: str) -> datetime:
    return datetime.strptime(session_time_str, "%Y-%m-%d_%H:%M:%S")


def build_tutorials(raw_tutorials: List[Dict[str, Any]]) -> List[Tutorial]:
    return [
        Tutorial(
            id=item["UID"],
            title=item["title"],
            organizers=item["organizers"],
            abstract=item["abstract"],
            website=item["website"],
            material=item["material"],
            slides=item["slides"],
            prerecorded=item.get("prerecorded", ""),
            rocketchat_channel=item.get("rocketchat_channel", ""),
            sessions=[
                TutorialSessionInfo(
                    session_name=session.get("name"),
                    start_time=session.get("start_time"),
                    end_time=session.get("start_time"),
                    livestream_id=session.get("livestream_id"),
                    zoom_link=session.get("zoom_link"),
                )
                for session in item.get("sessions")
            ],
            virtual_format_description=item["info"],
        )
        for item in raw_tutorials
    ]


def build_workshops(
    raw_workshops: List[Dict[str, Any]],
    raw_workshop_papers: Dict[str, List[Dict[str, Any]]],
    workshop_schedules: Dict[str, List[Dict[str, Any]]],
) -> List[Workshop]:

    workshop_papers: DefaultDict[str, List[WorkshopPaper]] = defaultdict(list)
    for workshop_id, papers in raw_workshop_papers.items():
        for item in papers:
            workshop_papers[workshop_id].append(
                WorkshopPaper(
                    id=item["UID"],
                    title=item["title"],
                    speakers=item["speakers"],
                    presentation_id=item.get("presentation_id", ""),
                )
            )

    workshops: List[Workshop] = [
        Workshop(
            id=item["UID"],
            title=item["title"],
            day=item["day"],
            organizers=item["organizers"],
            abstract=item["abstract"],
            website=item["website"],
            livestream=item["livestream"],
            papers=workshop_papers[item["UID"]],
            schedule=workshop_schedules.get(item["UID"]),
            rocketchat_channel=item["rocketchat_channel"],
            sessions=[
                SessionInfo(
                    session_name=session.get("name", ""),
                    start_time=session.get("start_time"),
                    end_time=session.get("end_time"),
                    zoom_link=session.get("zoom_link", ""),
                )
                for session in item.get("sessions")
            ],
        )
        for item in raw_workshops
    ]

    return workshops


def build_socials(raw_socials: List[Dict[str, Any]]) -> List[SocialEvent]:
    return [
        SocialEvent(
            id=item["UID"],
            name=item["name"],
            description=item["description"],
            image=item["image"],
            organizers=SocialEventOrganizers(
                members=item["organizers"]["members"],
                website=item["organizers"].get("website", ""),
            ),
            sessions=[
                SessionInfo(
                    session_name=session.get("name"),
                    start_time=parse_session_time(session.get("start_time")),
                    end_time=parse_session_time(session.get("end_time")),
                    zoom_link=session.get("zoom_link"),
                )
                for session in item["sessions"]
            ],
            rocketchat_channel=item.get("rocketchat_channel", ""),
            website=item.get("website", ""),
        )
        for item in raw_socials
    ]


def build_sponsors(site_data, by_uid, display_time_format) -> None:
    by_uid["sponsors"] = {}

    for sponsor in site_data["sponsors"]:
        uid = "_".join(sponsor["name"].lower().split())
        sponsor["UID"] = uid
        by_uid["sponsors"][uid] = sponsor

    # Format the session start and end times
    for sponsor in by_uid["sponsors"].values():
        sponsor["zoom_times"] = OrderedDict()

        for zoom in sponsor.get("schedule", []):
            start = zoom["start"].astimezone(pytz.timezone("GMT"))
            if zoom.get("end") is None:
                end = start + timedelta(hours=zoom["duration"])
            else:
                end = zoom["end"].astimezone(pytz.timezone("GMT"))
            day = start.strftime("%A")
            start_time = start.strftime(display_time_format)
            end_time = end.strftime(display_time_format)
            time_string = "{} ({}-{} GMT)".format(day, start_time, end_time)

            if day not in sponsor["zoom_times"]:
                sponsor["zoom_times"][day] = []

            sponsor["zoom_times"][day].append((time_string, zoom["label"]))

    # In the YAML, we just have a list of sponsors. We group them here by level
    sponsors_by_level: DefaultDict[str, List[Any]] = defaultdict(list)
    for sponsor in site_data["sponsors"]:
        if "level" in sponsor:
            sponsors_by_level[sponsor["level"]].append(sponsor)
        elif "levels" in sponsor:
            for level in sponsor["levels"]:
                sponsors_by_level[level].append(sponsor)

    site_data["sponsors_by_level"] = sponsors_by_level
    site_data["sponsor_levels"] = [
        "Diamond",
        "Platinum",
        "Gold",
        "Silver",
        "Bronze",
        "Supporter",
        "Publisher",
        "Diversity & Inclusion: Champion",
        "Diversity & Inclusion: In-Kind",
    ]

    assert all(lvl in site_data["sponsor_levels"] for lvl in sponsors_by_level)
