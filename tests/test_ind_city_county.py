from datetime import datetime
from os.path import dirname, join

import pytest  # noqa
from city_scrapers_core.constants import COMMITTEE, TENTATIVE
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_city_county import IndCityCountySpider

test_response = file_response(
    join(dirname(__file__), "files", "ind_city_county.jsonp"),
    url="https://calendar.indy.gov/handlers/query.ashx?get=eventlist&page=0&pageSize=-1&total=-1&view=list.xslt",  # noqa
)
spider = IndCityCountySpider()

freezer = freeze_time("2024-02-07")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_count():
    assert len(parsed_items) == 53


def test_title():
    assert parsed_items[0]["title"] == "Parks and Recreation Committee"


def test_description():
    assert (
        parsed_items[0]["description"]
        == "Monthly meeting of the Parks and Recreation Committee of the City-County Council to consider pending legislation"  # noqa
    )


def test_start():
    assert parsed_items[0]["start"] == datetime(2024, 2, 8, 17, 30)


def test_end():
    assert parsed_items[0]["end"] is None


def test_time_notes():
    assert parsed_items[0]["time_notes"] == ""


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_city_county/202402081730/x/parks_and_recreation_committee"
    )


def test_status():
    assert parsed_items[0]["status"] == TENTATIVE


def test_location():
    assert parsed_items[0]["location"] == {
        "name": "City-County Building, Meeting Room 260",
        "address": "200 East Washington Street, Indianapolis, IN, 46204",
    }


def test_source():
    assert (
        parsed_items[0]["source"]
        == "https://calendar.indy.gov/handlers/query.ashx?get=eventlist&page=0&pageSize=-1&total=-1&view=list.xslt"  # noqa
    )


def test_links():
    assert parsed_items[0]["links"] == [
        {
            "href": "https://calendar.indy.gov/event/parks-and-recreation-committee-14/",  # noqa
            "title": "Event Details",
        }
    ]


def test_classification():
    assert parsed_items[0]["classification"] == COMMITTEE


def test_all_day():
    assert parsed_items[0]["all_day"] is False
