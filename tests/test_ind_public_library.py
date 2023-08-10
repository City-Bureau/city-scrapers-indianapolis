from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_public_library import IndPublicLibrarySpider

test_response = file_response(
    join(dirname(__file__), "files", "ind_public_library.html"),
    url="https://www.indypl.org/about-the-library/board-meeting-times-committees",
)
spider = IndPublicLibrarySpider()

freezer = freeze_time("2023-08-10")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


"""
def test_tests():
    print("Please write some tests for this spider or at least disable this one.")
    assert False
Uncomment below
"""


def test_title():
    assert parsed_items[0]["title"] == "Indianapolis Public Library Board Of Trustees"


def test_description():
    assert parsed_items[0]["description"] == ""


def test_start():
    assert parsed_items[0]["start"] == datetime(2023, 1, 17, 14, 30)


# def test_end():
#     assert parsed_items[0]["end"] == datetime(2019, 1, 1, 0, 0)


def test_time_notes():
    assert (
        parsed_items[0]["time_notes"]
        == "Meetings are usually held at 6:30pm on the fourth Monday of the month, please check if the time has changed as specified in the following: January 17 - Special Meeting - Noon"  # noqa
    )


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_public_library/202301171430/x/indianapolis_public_library_board_of_trustees"  # noqa
    )


def test_status():
    assert parsed_items[0]["status"] == "passed"


def test_location():
    assert parsed_items[0]["location"] == {
        "name": "Special Meeting - Noon",
        "address": "",
    }


def test_source():
    assert (
        parsed_items[0]["source"]
        == "https://www.indypl.org/about-the-library/board-meeting-times-committees"
    )


def test_links():
    assert parsed_items[0]["links"] == [
        {"href": "https://youtu.be/hTEb_rJQB08", "title": "Link to livestream"},
        {"href": "https://www.indypl.org/locations", "title": "Library locations"},
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
