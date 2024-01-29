from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_school_board import IndSchoolBoard

test_response = file_response(
    join(dirname(__file__), "files", "ind_school_board.xml"),
    url="https://go.boarddocs.com/in/indps/Board.nsf/XML-ActiveMeetings",
)
spider = IndSchoolBoard()

freezer = freeze_time("2023-08-05")
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
    assert parsed_items[0]["title"] == "Indianapolis Public School Board"


def test_description():
    assert (
        parsed_items[0]["description"]
        == "Please check website for meeting info. Contact Leslie-Ann James for questions (317-226-4418)"  # noqa
    )


def test_start():
    assert parsed_items[0]["start"] == datetime(2023, 1, 9, 0, 0)


# def test_end():
#     assert parsed_items[0]["end"] == datetime(2019, 1, 1, 0, 0)


def test_time_notes():
    assert parsed_items[0]["time_notes"] == ""


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_school_board/202301090000/x/indianapolis_public_school_board"
    )


def test_status():
    assert parsed_items[0]["status"] == "passed"


def test_location():
    assert parsed_items[0]["location"] == {
        "name": "",
        "address": "",
    }


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
