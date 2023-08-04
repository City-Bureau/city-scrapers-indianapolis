from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndIiaSpider(CityScrapersSpider):
    name = "ind_iia"
    agency = "Indianapolis International Airport Board"
    timezone = "America/Chicago"
    start_urls = ["https://www.ind.com/about/leadership/board-papers-documentation"]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        for item in response.css(".blog__listing"):
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
        """Parse or generate meeting title."""
        title = "Indianapolis International Airport Board"
        return title

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        description = ""
        return description

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        try:
            "Date & Time:" in item.css(
                "div p:nth-child(3) strong:nth-child(1)::text"
            ).get()
            string = item.css("div p:nth-child(3)::text").get()
        except TypeError:
            string = item.css("div p:nth-child(4)::text").get()

        start_date = string.split("at")[0].strip()  # noqa
        start_time = string.split("at")[1].strip()

        return parser().parse(start_date + " " + start_time)

    def _parse_end(self, item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        return ""

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        try:
            "Board Room (Room 11T.413)" in item.css("div p:nth-child(2)::text").get()
            name = "Airport Board Room (Room 11T.413)"
            address = "7800 Col. H. Weir Cook Memorial Drive, Indianapolis, IN 46241"
        except TypeError:
            name = "Please check meeting website for location"
            address = None

        return {
            "address": address,
            "name": name,
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        zoom_link = item.css("div p:nth-child(3) a::attr(href)").get()
        meeting_page = item.css("div div a::attr(href)").get()

        return [
            {
                "href": meeting_page,
                "title": "Meeting Page",
            },
            {
                "href": zoom_link,
                "title": "Zoom Link",
            },
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
