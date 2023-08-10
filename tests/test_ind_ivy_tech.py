from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_ivy_tech import IndIvyTechSpider

test_response = file_response(
    join(dirname(__file__), "files", "ind_ivy_tech.html"),
    url="https://www.ivytech.edu/about-ivy-tech/college-operations/state-board-of-trustees/",  # noqa
)
spider = IndIvyTechSpider()

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
    assert (
        parsed_items[0]["title"] == "Ivy Tech Community College State Board of Trustees"
    )


def test_description():
    assert parsed_items[0]["description"] == ""


def test_start():
    assert parsed_items[0]["start"] == datetime(2023, 2, 1, 0, 0)


# def test_end():
#     assert parsed_items[0]["end"] == datetime(2019, 1, 1, 0, 0)


def test_time_notes():
    assert (
        parsed_items[0]["time_notes"]
        == "The State Board meets for a few days on a bimonthly basis. Refer to the links for specific times and locations."  # noqa
    )


def test_id():
    assert (
        parsed_items[0]["id"]
        == "ind_ivy_tech/202302010000/x/ivy_tech_community_college_state_board_of_trustees"  # noqa
    )


def test_status():
    assert parsed_items[0]["status"] == "passed"


def test_location():
    assert parsed_items[0]["location"] == {"name": "", "address": ""}


def test_source():
    assert (
        parsed_items[0]["source"]
        == "https://www.ivytech.edu/about-ivy-tech/college-operations/state-board-of-trustees/"  # noqa
    )


def test_links():
    assert parsed_items[0]["links"] == [
        {
            "href": "ivytech.edu/media/4bgifvo0/february-2023-official-notice-of-meeting.pdf",  # noqa
            "title": "Link 1",
        },
        {
            "href": "ivytech.edu/media/241esguz/february2023-agenda.pdf",
            "title": "Link 2",
        },
        {
            "href": "ivytech.edu/media/rj1avj1c/february-2023-board-minutes.pdf",
            "title": "Link 3",
        },
        {
            "href": "ivytech.edu/media/lovp2hnz/february-2023-booklet.pdf",
            "title": "Link 4",
        },
        {
            "href": "https://www.ivytech.edu/about-ivy-tech/college-operations/state-board-of-trustees/",  # noqa
            "title": "Meeting Page",
        },
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
