from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, TENTATIVE
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_indygo_finance import IndIndygoFinanceSpider

test_response = file_response(
    join(dirname(__file__), "files", "ind_indygo_finance.html"),
    url="https://www.indygo.net/about-indygo/board-of-directors/",
)
spider = IndIndygoFinanceSpider()

freezer = freeze_time("2023-08-10")
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
    assert parsed_items[0]["title"] == "IndyGo Finance Committee"


def test_description():
    assert parsed_items[0]["description"] == ""


def test_start():
    assert parsed_items[0]["start"] == datetime(2024, 1, 18, 8, 30)


def test_end():
    assert parsed_items[0]["end"] is None


def test_time_notes():
    assert parsed_items[0]["time_notes"] == ""


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_indygo_finance/202401180830/x/indygo_finance_committee"
    )


def test_status():
    assert parsed_items[0]["status"] == TENTATIVE


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
            "href": "https://www.indygo.net/about-indygo/board-of-directors/",
            "title": "Meeting Page",
        },
        {
            "href": "https://public.onboardmeetings.com/Group/HrdLpC4rmFdYrgplGJZm82TtkS14OCvw7QLcFFPpPrIA/PBtWHdxtJt6XgVphYPHNTSsJFC992FZbLhKOoPeFrjsA",  # noqa
            "title": "Past Finance Committee packets",
        },
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
