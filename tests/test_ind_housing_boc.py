from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, CANCELLED
from city_scrapers_core.items import Meeting
from city_scrapers_core.utils import file_response
from freezegun import freeze_time
from scrapy.http import HtmlResponse

from city_scrapers.spiders.ind_housing_boc import IndHousingBocSpider


@pytest.fixture
def spider():
    spider = IndHousingBocSpider()
    spider.archive_datetimes = set()
    return spider


@pytest.fixture
def upcoming_response():
    return file_response(
        join(dirname(__file__), "files", "ind_housing_boc_upcoming.html"),
        url="https://www.indyhousing.org/calendar/boc-meeting-september-15-2026",
    )


@pytest.fixture
def archive_response():
    return file_response(
        join(dirname(__file__), "files", "ind_housing_boc_archive.html"),
        url="https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026",  # noqa
    )


@pytest.fixture
def upcoming_items(spider, upcoming_response):
    with freeze_time("2026-08-31"):
        return [item for item in spider.parse(upcoming_response)]


@pytest.fixture
def archive_items(spider, archive_response):
    with freeze_time("2026-08-31"):
        return [item for item in spider.parse(archive_response)]


# --- upcoming (calendar) meeting tests -------------------------------------


def test_upcoming_title(upcoming_items):
    assert upcoming_items[0]["title"] == "BOC Meeting"


def test_upcoming_description(upcoming_items):
    assert upcoming_items[0]["description"] == ""


def test_upcoming_start(upcoming_items):
    assert upcoming_items[0]["start"] == datetime(2026, 9, 15, 13, 0)


def test_upcoming_end(upcoming_items):
    assert upcoming_items[0]["end"] is None


def test_upcoming_time_notes(upcoming_items):
    assert upcoming_items[0]["time_notes"] == ""


def test_upcoming_id(upcoming_items):
    assert upcoming_items[0]["id"] == "ind_housing_boc/202609151300/x/boc_meeting"


def test_upcoming_status(upcoming_items):
    assert upcoming_items[0]["status"] == "tentative"


def test_upcoming_location(upcoming_items):
    assert upcoming_items[0]["location"] == {
        "name": "Indianapolis Housing Agency",
        "address": "1935 N. Meridian Street, Indianapolis, IN 46202",
    }


def test_upcoming_source(upcoming_items):
    assert (
        upcoming_items[0]["source"]
        == "https://www.indyhousing.org/calendar/boc-meeting-september-15-2026"
    )


def test_upcoming_links(upcoming_items):
    assert upcoming_items[0]["links"] == []


def test_upcoming_classification(upcoming_items):
    assert upcoming_items[0]["classification"] == BOARD


def test_upcoming_all_day(upcoming_items):
    assert upcoming_items[0]["all_day"] is False


# --- archive (past) meeting tests -------------------------------------------


def test_archive_title(archive_items):
    assert archive_items[0]["title"] == "Board of Commissioners Meeting"


def test_archive_description(archive_items):
    assert archive_items[0]["description"] == ""


def test_archive_start(archive_items):
    assert archive_items[0]["start"] == datetime(2026, 2, 17, 13, 0)


def test_archive_end(archive_items):
    assert archive_items[0]["end"] is None


def test_archive_time_notes(archive_items):
    assert archive_items[0]["time_notes"] == ""


def test_archive_id(archive_items):
    assert (
        archive_items[0]["id"]
        == "ind_housing_boc/202602171300/x/board_of_commissioners_meeting"
    )


def test_archive_status(archive_items):
    assert archive_items[0]["status"] == "passed"


def test_archive_location(archive_items):
    assert archive_items[0]["location"] == {
        "name": "Indianapolis Housing Agency",
        "address": "1935 N. Meridian Street, Indianapolis, IN 46202",
    }


def test_archive_source(archive_items):
    assert (
        archive_items[0]["source"]
        == "https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026"  # noqa
    )


def test_archive_links(archive_items):
    assert archive_items[0]["links"] == [
        {
            "href": "https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026",  # noqa
            "title": "Meeting Attachment",
        }
    ]


# Test that cancelled meetings are correctly identified
def test_cancelled_title_sets_status(spider):
    raw = "BOC Meeting - Cancelled | 09/15/2026"
    meeting = Meeting(
        title=spider._strip_title_suffix(raw),
        description="",
        start=datetime(2026, 9, 15, 13, 0),
    )
    assert meeting["title"] == "BOC Meeting"
    assert spider._get_status(meeting, text=raw) == CANCELLED


def test_archive_classification(archive_items):
    assert archive_items[0]["classification"] == BOARD


def test_archive_all_day(archive_items):
    assert archive_items[0]["all_day"] is False


# --- non-board event (Landlord Workshop) tests -------------------------------


def _workshop_response(longtext=None, location_widget=None):
    """Load the saved Landlord Workshop page, optionally injecting location
    markup (the live page has an empty Location widget and the venue only
    appears inside the flyer image)."""
    with open(join(dirname(__file__), "files", "ind_housing_boc_workshop.html")) as f:
        body = f.read()
    if longtext:
        body = body.replace(
            "</p></div>\n<!-- Location Widget -->",
            f"</p><p>{longtext}</p></div>\n<!-- Location Widget -->",
            1,
        )
    if location_widget:
        body = body.replace("||||||-->", f"||||||-->\n{location_widget}", 1)
    return HtmlResponse(
        url="https://www.indyhousing.org/calendar/landlord-workshop",
        body=body,
        encoding="utf-8",
    )


def _parse_one(spider, response):
    with freeze_time("2026-09-01"):
        return list(spider.parse(response))[0]


def test_workshop_fixture_basics(spider):
    item = _parse_one(spider, _workshop_response())
    assert item["title"] == "Landlord Workshop"
    assert item["start"] == datetime(2026, 9, 22, 13, 0)
    # The live page's Location widget is empty (venue is only in the flyer image)
    assert item["location"] == {"name": "Indianapolis Housing Agency", "address": ""}


def test_address_without_comma_before_city(spider):
    response = _workshop_response(
        longtext="Location | 1919 N. Meridian Street Indianapolis, IN 46202"
    )
    item = _parse_one(spider, response)
    assert item["location"] == {
        "name": "Indianapolis Housing Agency",
        "address": "1919 N. Meridian Street Indianapolis, IN 46202",
    }


def test_address_from_location_widget_preferred(spider):
    response = _workshop_response(
        longtext="Location | Somewhere else",
        location_widget=(
            "<div class='col-lg-12 css_hook_location'><strong>Address</strong>: "
            "1919 N. Meridian Street Indianapolis, IN 46202</div>"
        ),
    )
    item = _parse_one(spider, response)
    assert item["location"]["address"] == (
        "1919 N. Meridian Street Indianapolis, IN 46202"
    )


def test_address_regex_tolerates_missing_comma(spider):
    text = "Join us at 1919 N. Meridian Street Indianapolis, IN 46202 for lunch"
    assert spider.ADDRESS_RE.search(text).group(0).startswith("1919 N. Meridian")


def test_other_venue_not_labeled_as_agency(spider):
    response = _workshop_response(
        location_widget=(
            "<div class='col-lg-12 css_hook_location'><strong>Address</strong>: "
            "200 E. Washington Street, Indianapolis, IN 46204</div>"
        ),
    )
    item = _parse_one(spider, response)
    assert item["location"] == {
        "name": "",
        "address": "200 E. Washington Street, Indianapolis, IN 46204",
    }
