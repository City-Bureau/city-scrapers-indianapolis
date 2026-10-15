import json
from datetime import datetime
from os.path import dirname, join
from types import SimpleNamespace

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.utils import file_response
from freezegun import freeze_time
from scrapy.http import Request, Response

from city_scrapers.spiders.ind_cpcb import IndCpcbSpider

SOURCE_URL = "https://www.indy.gov/activity/citizens-police-complaint-board"


NOTICE_TEXT = """MEETING NOTICE
INDIANAPOLIS CITIZENS' POLICE COMPLAINT BOARD
May 11, 2026

Notice is hereby given that the Citizens' Police Complaint Board will hold a public
meeting on:

\u2022 Monday, May 11, 2026
\u2022 at 6:00 p.m.
\u2022 at the City-County Building
\u2022 200 E. Washington Street, Indianapolis, IN 46204
\u2022 in Room T-310

For accommodations needed by persons with disabilities planning to attend this
public hearing, please call the Office of Disability Affairs at (317) 327-5654.
"""


def make_pdf(text):
    """A minimal one-page PDF whose text layer is `text`."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = [ln for ln in escaped.splitlines()]
    stream = "BT /F1 10 Tf 12 TL 40 760 Td\n"
    stream += "\n".join(f"({ln}) '" for ln in lines) + "\nET"
    stream = stream.encode("cp1252", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        xref,
    )
    return out


@pytest.fixture(scope="module")
def parsed_items():
    test_response = file_response(
        join(dirname(__file__), "files", "ind_cpcb.json"),
        url=SOURCE_URL,
    )
    spider = IndCpcbSpider()
    items = []
    with freeze_time("2026-08-31"):
        for result in spider.parse(test_response):
            if not isinstance(result, Request):
                items.append(result)
                continue
            meeting = result.cb_kwargs["meeting"]
            if meeting["start"] == datetime(2026, 5, 11, 18, 0):
                # the notice downloads fine
                notice = Response(result.url, body=make_pdf(NOTICE_TEXT))
                items.extend(spider._parse_notice(notice, meeting=meeting))
            else:
                # every other notice fails to download
                failure = SimpleNamespace(request=result, value="boom")
                items.extend(spider._notice_failed(failure))
    return items


@pytest.fixture(scope="module")
def first_meeting(parsed_items):
    # furthest-out 2026 date, no documents yet
    return parsed_items[0]


@pytest.fixture(scope="module")
def documented_meeting(parsed_items):
    # past meeting with all four documents
    return next(
        item for item in parsed_items if item["start"] == datetime(2026, 5, 11, 18, 0)
    )


def test_count(parsed_items):
    assert len(parsed_items) == 73


def test_title(first_meeting):
    assert first_meeting["title"] == "Citizens' Police Complaint Board"


def test_description(first_meeting):
    assert first_meeting["description"] == ""


def test_classification(first_meeting):
    assert first_meeting["classification"] == BOARD


def test_start(first_meeting):
    assert first_meeting["start"] == datetime(2026, 12, 14, 18, 0)


def test_end(first_meeting):
    assert first_meeting["end"] is None


def test_all_day(parsed_items):
    assert all(item["all_day"] is False for item in parsed_items)


def test_time_notes(first_meeting):
    assert first_meeting["time_notes"] == (
        "The board generally meets on the second Monday of each month at "
        "6:00 p.m., but no less than quarterly, to conduct business. "
        "Please check the meeting notice attachment for meeting location and start time details."  # noqa
    )


def test_location(documented_meeting):
    # read from the meeting notice
    assert documented_meeting["location"] == {
        "name": "City-County Building, Room T-310",
        "address": "200 E. Washington Street, Indianapolis, IN 46204",
    }


def test_location_unknown_without_notice(first_meeting):
    # the agency's office address is not the meeting location
    assert first_meeting["location"] == {"name": "TBD", "address": ""}


def test_notice_requests():
    spider = IndCpcbSpider()
    response = file_response(
        join(dirname(__file__), "files", "ind_cpcb.json"), url=SOURCE_URL
    )
    results = list(spider.parse(response))
    meetings = [r for r in results if isinstance(r, Meeting)]
    requests = [r for r in results if isinstance(r, Request)]
    assert len(meetings) + len(requests) == 73
    assert len(requests) == 56
    # one notice covers two January 2021 meetings; neither may be deduplicated
    assert all(r.dont_filter for r in requests)
    assert all(m["location"] == {"name": "TBD", "address": ""} for m in meetings)


@pytest.mark.parametrize(
    "lines,expected",
    [
        (
            [
                "Monday, March 9, 2026",
                "at 6:00 p.m.",
                "at the Indianapolis Public Library \u2013 Beech Grove Branch",
                "1102 Main Street, Beech Grove, IN 46107",
                "in the Community Room",
            ],
            {
                "name": "Indianapolis Public Library \u2013 Beech Grove Branch, "
                "Community Room",
                "address": "1102 Main Street, Beech Grove, IN 46107",
            },
        ),
        (
            # place and address share a bullet, no zip, ordinal split by a space
            [
                "Monday, November 18, 2024",
                "at 6:00 p.m.",
                "at Fay Biccard Glick Neighborhood Center, 2990 W 71 st St, "
                "Indianapolis, IN",
                "in the Gymnasium",
            ],
            {
                "name": "Fay Biccard Glick Neighborhood Center, Gymnasium",
                "address": "2990 W 71st St, Indianapolis, IN",
            },
        ),
        (
            # older format, no city or state; room change note dropped
            [
                "Monday, October 11, 2021,",
                "at 6:00 pm.",
                "in the City County Building, 200 East Washington Street,",
                "Room 260 \u2013 PLEASE NOTE ROOM CHANGE",
            ],
            {
                "name": "City County Building, Room 260",
                "address": "200 East Washington Street, Indianapolis, IN",
            },
        ),
        (
            # nested bullet address with only a zip, time listed last
            [
                "On Monday, July 11, 2022",
                "At the CJC Assessment and Intervention Center",
                "o 2979 East Pleasant Run Parkway, 46203",
                "At 6:00 pm",
            ],
            {
                "name": "CJC Assessment and Intervention Center",
                "address": "2979 East Pleasant Run Parkway, Indianapolis, IN 46203",
            },
        ),
        (
            [
                "Monday, September 13, 2021",
                "at 6:00 pm.",
                "located at 40 West 40th Street, Indianapolis, IN 46208",
            ],
            None,  # no place name
        ),
    ],
)
def test_parse_notice_location(lines, expected):
    text = (
        "MEETING NOTICE\nNotice is hereby given that the Board will hold a public\n"
        "meeting on:\n"
        + "\n".join(ln if ln.startswith("o ") else f"\u2022 {ln}" for ln in lines)
        + "\nFor accommodations needed by persons with disabilities"
    )
    assert IndCpcbSpider()._parse_notice_location(text) == expected


def test_parse_notice_location_virtual():
    text = (
        "Notice is hereby given that the Board will hold a virtual public\n"
        "meeting on Monday, April 12, 2021, beginning at 6:00 pm. via Webex:\n"
        "Event address for attendees: https://indy.webex.com/x\n"
        "For accommodations needed by persons"
    )
    assert IndCpcbSpider()._parse_notice_location(text) == {
        "name": "Online (Webex)",
        "address": "",
    }


def test_parse_notice_location_unparseable():
    assert IndCpcbSpider()._parse_notice_location("") is None
    assert IndCpcbSpider()._parse_notice_location("Nothing useful here") is None


def test_unreadable_notice_keeps_unknown_location():
    spider = IndCpcbSpider()
    meeting = {"location": {"name": "TBD", "address": ""}}
    response = Response("https://example.com/n.pdf", body=b"not a pdf")
    (result,) = spider._parse_notice(response, meeting=meeting)
    assert result["location"] == {"name": "TBD", "address": ""}


def test_source(first_meeting):
    assert first_meeting["source"] == SOURCE_URL


def test_id(documented_meeting):
    assert (
        documented_meeting["id"]
        == "ind_cpcb/202605111800/x/citizens_police_complaint_board"
    )


def test_links(documented_meeting):
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


def test_status_passed(documented_meeting):
    assert documented_meeting["status"] == "passed"


def test_status_tentative(first_meeting):
    assert first_meeting["status"] == "tentative"


def test_status_cancelled(parsed_items):
    # "No Meeting" months
    cancelled = [item for item in parsed_items if item["status"] == "cancelled"]
    assert len(cancelled) == 13
    assert all(item["links"] == [] for item in cancelled)


def test_year_taken_from_accordion(parsed_items):
    # source has a mistyped "May 13, 2023" in the 2024 accordion
    starts = {item["start"] for item in parsed_items}
    assert datetime(2024, 5, 13, 18, 0) in starts
    assert datetime(2023, 5, 13, 18, 0) not in starts


def test_non_monday_meetings_kept(parsed_items):
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
