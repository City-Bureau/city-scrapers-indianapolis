from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.indianapolis_indygo_board import (
    IndianapolisIndygoBoardSpider,
)

test_response = file_response(
    join(dirname(__file__), "files", "indianapolis_indygo_board.html"),
    url="https://www.indygo.net/about-indygo/board-of-directors/",
)
spider = IndianapolisIndygoBoardSpider()

freezer = freeze_time("2023-07-22")
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
    assert parsed_items[0]["title"] == "IndyGo Board"


def test_description():
    assert (
        parsed_items[0]["description"]
        == "– Board of Finance Meeting following immediately after the Board of Directors meeting."  # noqa
    )


def test_start():
    assert parsed_items[0]["start"] == datetime(2023, 1, 26, 17, 0)


# def test_end():
#     assert parsed_items[0]["end"] == datetime(2019, 1, 1, 0, 0)


def test_time_notes():
    assert (
        parsed_items[0]["time_notes"]
        == "Board meetings are set for 5:00PM unless otherwise noted in meeting description. Please double check the website before the meeting date."  # noqa
    )


def test_id():
    assert (
        parsed_items[0]["id"] == "indianapolis_indygo_board/202301261700/x/indygo_board"
    )


def test_status():
    assert parsed_items[0]["status"] == "passed"


def test_location():
    assert parsed_items[0]["location"] == {
        "name": "Administrative Office - Board Room",
        "address": "1501 W. Washington St. Indianapolis, IN 46222",
    }


def test_source():
    assert (
        parsed_items[0]["source"]
        == "https://www.indygo.net/about-indygo/board-of-directors/"
    )


def test_links():
    assert parsed_items[0]["links"] == [
        {
            "href": "https://www.facebook.com/IndyGoBus/",
            "title": "Facebook page for meeting livestream",
        }
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
