"""
#scrape board docs using mixin
# advantage is this method is quicker because other method scrapes entire xml file
# also the mixin is a cleaner method using POST requests.

from city_scrapers_core.spiders import CityScrapersSpider

from ..mixins.boarddocs import BoardDocsMixin
from city_scrapers_core.spiders import CityScrapersSpider

class IndSchoolBoard(BoardDocsMixin, CityScrapersSpider):
    name = "ind_school_board"
    agency = "Indianapolis Public School Board"
    timezone = "America/New_York"
    boarddocs_slug = "indps"
    boarddocs_committee_id = "AAL86A1CBDD0"

    def augment_meeting(self, meeting, item):
        print(item)

"""
# Here is board docs page scraped using an alternative method demonstrated here.
# Advantage is this method has the agenda link:
# https://github.com/City-Bureau/city-scrapers-cle/blob/105ed65078ab4f7ca54193cc54c8c52dc174d08b/city_scrapers/spiders/cle_metro_school_district.py#L13

import re
import datetime

from city_scrapers_core.constants import BOARD, FORUM
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndSchoolBoard(CityScrapersSpider):
    name = "ind_school_board"
    agency = "Indianapolis Public School Board"
    timezone = "America/Detroit"
    start_urls = ["https://go.boarddocs.com/in/indps/Board.nsf/XML-ActiveMeetings"]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """

        for item in response.xpath("//meeting"):
            agenda_url = item.xpath("./link/text()").extract_first()
            links = []
            
            if agenda_url:
                links = [{"title": "Agenda", "href": agenda_url}]
                meeting = Meeting(
                    title=self._parse_title(item),
                    description=self._parse_description(item),  # noqa
                    classification=self._parse_classification(item),
                    start=self._parse_start(item),
                    end=None,
                    all_day=False,
                    time_notes="",
                    location=self._parse_location(item),
                    links=links,
                    source=agenda_url or response.url,
                )

                meeting["status"] = self._get_status(meeting)
                #meeting["status"] = 'passed'
                meeting["id"] = self._get_id(meeting)

                yield meeting
            else:
                continue

    def _parse_title(self, item):
        """Parse or generate meeting title."""
        title = "Indianapolis Public School Board"
        return title

    def _parse_description(self, item):
        description = ""
        if item.xpath("./description/text()").extract_first() != "":
            description = item.xpath("./description/text()").extract_first()

        return description

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        title_str = item.xpath("./name/text()").extract_first()
        if "Community" in title_str:
            return FORUM
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""

        title_str = item.xpath("./name/text()").extract_first()
        time_match = re.search(r"\d{1,2}:\d{1,2} *[APM\.]{2,4}", title_str)
        if time_match:
            time_str = time_match.group().replace(".", "")
        else:
            time_str = "00:00:00"

        date = item.xpath("./start/date/text()").extract_first()
        
        #return datetime.strptime(" ".join([date_str, time_str]), "%Y-%m-%d %I:%M %p")
        return parser().parse(date + " " + time_str)

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "",
            "name": "",
        }
