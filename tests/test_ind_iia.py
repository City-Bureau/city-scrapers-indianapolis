from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_iia import IndIiaSpider

test_response = file_response(
    join(dirname(__file__), "files", "ind_iia.html"),
    url="https://www.ind.com/about/leadership/board-papers-documentation",
)
spider = IndIiaSpider()

freezer = freeze_time("2023-08-04")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


"""
Uncomment below

def test_tests():
    print("Please write some tests for this spider or at least disable this one.")
    assert False
"""


def test_title():
    assert parsed_items[0]["title"] == "Indianapolis International Airport Board"


def test_description():
    assert parsed_items[0]["description"] == ""


def test_start():
    assert parsed_items[0]["start"] == datetime(2023, 7, 21, 8, 0)


# def test_end():
#     assert parsed_items[0]["end"] == datetime(2019, 1, 1, 0, 0)


def test_time_notes():
    assert parsed_items[0]["time_notes"] == ""


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_iia/202307210800/x/indianapolis_international_airport_board"
    )


def test_status():
    assert parsed_items[0]["status"] == "passed"


def test_location():
    assert parsed_items[0]["location"] == {
        "name": "Airport Board Room (Room 11T.413)",
        "address": "7800 Col. H. Weir Cook Memorial Drive, Indianapolis, IN 46241",
    }


def test_source():
    assert (
        parsed_items[0]["source"]
        == "https://www.ind.com/about/leadership/board-papers-documentation"
    )


def test_links():
    assert parsed_items[0]["links"] == [
        {"href": "https://tinyurl.com/IAAJuly2023Board", "title": "Meeting Page"},
        {"href": "https://tinyurl.com/IAAJuly2023Board", "title": "Zoom Link"},
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
