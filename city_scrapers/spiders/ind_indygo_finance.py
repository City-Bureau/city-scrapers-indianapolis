from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndIndygoFinanceSpider(CityScrapersSpider):
    name = "ind_indygo_finance"
    agency = "Indianapolis Indygo Finance Committee"
    timezone = "America/Chicago"
    start_urls = ["https://www.indygo.net/about-indygo/board-of-directors/"]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        for item in response.css(".content-section:nth-child(6) ul li"):
            meeting = Meeting(
                title=self._parse_title(item),
                description=self._parse_description(item),
                classification=self._parse_classification(item),
                start=self._parse_start(item),
                end=self._parse_end(item),
                all_day=self._parse_all_day(item),
                time_notes=self._parse_time_notes(item),
                location=self._parse_location(item),
                links=self._parse_links(item),
                source=self._parse_source(response),
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_title(self, item):
        title = "IndyGo Finance Committee"
        return title

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        string = item.css("::text").get()
        string_split = string.split(" ")
        if len(string_split) > 3:
            description = string.split(" ", 3)[3]
        else:
            description = ""
        return description

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        string = item.css("::text").get()
        start_date = string.split(" ")[1] + " " + string.split(" ")[2] + " 2023"
        start_time = "08:30:00"
        return parser().parse(start_date + " " + start_time)

    def _parse_end(self, item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        return "Board meetings are set for 8:30AM unless otherwise noted in meeting description. Please double check the website before the meeting date."  # noqa

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "1501 W. Washington St. Indianapolis, IN 46222",
            "name": "Administrative Office - Board Room",
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        return [
            {
                "href": "https://www.indygo.net/about-indygo/board-of-directors/",
                "title": "Meeting Page",
            },
            {
                "href": "https://public.onboardmeetings.com/Group/HrdLpC4rmFdYrgplGJZm82TtkS14OCvw7QLcFFPpPrIA/PBtWHdxtJt6XgVphYPHNTSsJFC992FZbLhKOoPeFrjsA",  # noqa
                "title": "Past Finance Committee packets",
            },
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
