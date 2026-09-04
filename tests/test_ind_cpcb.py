import json
from datetime import datetime
from os.path import dirname, join

from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_cpcb import IndCpcbSpider

SOURCE_URL = "https://www.indy.gov/activity/citizens-police-complaint-board"

test_response = file_response(
    join(dirname(__file__), "files", "ind_cpcb.json"),
    url=SOURCE_URL,
)
spider = IndCpcbSpider()

freezer = freeze_time("2026-08-31")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()

# furthest-out 2026 date, no documents yet
first_meeting = parsed_items[0]

# past meeting with all four documents
documented_meeting = next(
    item for item in parsed_items if item["start"] == datetime(2026, 5, 11, 18, 0)
)


def test_count():
    assert len(parsed_items) == 73


def test_title():
    assert first_meeting["title"] == "Citizens' Police Complaint Board"


def test_description():
    assert first_meeting["description"] == ""


def test_classification():
    assert first_meeting["classification"] == BOARD


def test_start():
    assert first_meeting["start"] == datetime(2026, 12, 14, 18, 0)


def test_end():
    assert first_meeting["end"] is None


def test_all_day():
    assert all(item["all_day"] is False for item in parsed_items)


def test_time_notes():
    assert first_meeting["time_notes"] == (
        "The board generally meets on the second Monday of each month at "
        "6:00 p.m., but no less than quarterly, to conduct business."
    )


def test_location():
    assert first_meeting["location"] == {
        "name": "City-County Building",
        "address": "200 E. Washington St., Suite 1860, Indianapolis, IN 46204",
    }


def test_source():
    assert first_meeting["source"] == SOURCE_URL


def test_id():
    assert (
        documented_meeting["id"]
        == "ind_cpcb/202605111800/x/citizens_police_complaint_board"
    )


def test_links():
    assert documented_meeting["links"] == [
        {
            "href": "https://us-east-1-indy.graphassets.com/ActDBC5rvRWeCZlNNnLrDz/cmovxdt8h10m008lff348gw3k?dl=true",  # noqa
            "title": "Meeting Notice",
        },
        {
            "href": "https://us-east-1-indy.graphassets.com/ActDBC5rvRWeCZlNNnLrDz/cmoniqu6w4fc707ljwci6zlmc?dl=true",  # noqa
            "title": "Meeting Agenda",
        },
        {
            "href": "https://us-east-1-indy.graphassets.com/ActDBC5rvRWeCZlNNnLrDz/cmshu0oli0kqx07lix37a34xh?dl=true",  # noqa
            "title": "Meeting Minutes",
        },
        {
            "href": "https://us-east-1-indy.graphassets.com/ActDBC5rvRWeCZlNNnLrDz/cmshtqo8r0j6u07lkmpph5yjc?dl=true",  # noqa
            "title": "Voting Results",
        },
    ]


def test_status_passed():
    assert documented_meeting["status"] == "passed"


def test_status_tentative():
    assert first_meeting["status"] == "tentative"


def test_status_cancelled():
    # "No Meeting" months
    cancelled = [item for item in parsed_items if item["status"] == "cancelled"]
    assert len(cancelled) == 13
    assert all(item["links"] == [] for item in cancelled)


def test_year_taken_from_accordion():
    # source has a mistyped "May 13, 2023" in the 2024 accordion
    starts = {item["start"] for item in parsed_items}
    assert datetime(2024, 5, 13, 18, 0) in starts
    assert datetime(2023, 5, 13, 18, 0) not in starts


def test_non_monday_meetings_kept():
    # the board usually meets on a Monday, but the source lists a Tuesday
    # (2024-04-09) and a Saturday (2021-02-27) that must not be dropped
    starts = {item["start"] for item in parsed_items}
    assert datetime(2024, 4, 9, 18, 0) in starts
    assert datetime(2021, 2, 27, 18, 0) in starts


def test_start_request():
    request = next(IndCpcbSpider().start_requests())
    assert request.method == "POST"
    assert request.url == (
        "https://api-us-east-1-indy.graphcms.com/v2/ckp3xrh1i657g01xp53az2mv4/master"
    )
    body = json.loads(request.body)
    assert body["variables"]["slug"] == "citizens-police-complaint-board"
