import os
import shutil
from pathlib import Path

import wget

ROOT = Path(__file__).parent.absolute()
PATH_DOWNLOADS = ROOT / "downloads"
PATH_YAMLS = ROOT / "yamls"

URL_SLIDESLIVE_OTHER = "https://docs.google.com/spreadsheets/d/1Cp04DGRiDj8oY00-xDjTpjzCd_fjq3YhqOclhvFRK94/export?format=csv&gid=1157572740"
PATH_SLIDESLIVE_OTHER = PATH_DOWNLOADS / "slideslive_other.csv"

URL_TUTORIALS_SCHEDULE = "https://docs.google.com/spreadsheets/d/16kLECn6WZNXfbj_8CL1QJykHVndijMCcyWT3rl9jOhI/export?format=xlsx"
PATH_TUTORIALS_SCHEDULE = PATH_DOWNLOADS / "tutorials.xlsx"

URL_TUTORIALS_OVERVIEW = "https://raw.githubusercontent.com/emnlp2020/emnlp2020-website/master/src/data/tutorials.csv"
PATH_TUTORIALS_OVERVIEW = PATH_DOWNLOADS / "tutorials.csv"

PATH_DOWNLOADS.mkdir(exist_ok=True, parents=True)
PATH_YAMLS.mkdir(exist_ok=True, parents=True)


def download_file(url: str, out: Path):
    out.unlink(missing_ok=True)
    wget.download(url, str(out))


def download_slideslive():
    download_file(URL_SLIDESLIVE_OTHER, PATH_SLIDESLIVE_OTHER)


def download_tutorials():
    download_file(URL_TUTORIALS_SCHEDULE, PATH_TUTORIALS_SCHEDULE)
    download_file(URL_TUTORIALS_OVERVIEW, PATH_TUTORIALS_OVERVIEW)
