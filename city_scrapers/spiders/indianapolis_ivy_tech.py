from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndianapolisIvyTechSpider(CityScrapersSpider):
    name = "indianapolis_ivy_tech"
    agency = "Indianapolis Ivy Tech Board Of Trustees"
    timezone = "America/Chicago"
    start_urls = [
        "https://www.ivytech.edu/about-ivy-tech/college-operations/state-board-of-trustees/"  # noqa
    ]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        for item in response.css(
            "main div div:nth-child(4) .left-containers tr td:nth-child(1) p"
        ):
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
        title = "Ivy Tech Community College State Board of Trustees"
        return title

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        return ""

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        text = item.css("strong::text").get()
        start_date = text.split("-")[0] + " 2023"
        return parser().parse(start_date)

    def _parse_end(self, item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        return "The State Board meets for a few days on a bimonthly basis. Refer to the links for specific times and locations."  # noqa

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "",
            "name": "",
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        link_list = item.css("a::attr(href)").getall()

        try:
            link1 = "ivytech.edu" + link_list[0]
        except IndexError:
            link1 = ""

        try:
            link2 = "ivytech.edu" + link_list[1]
        except IndexError:
            link2 = ""

        try:
            link3 = "ivytech.edu" + link_list[2]
        except IndexError:
            link3 = ""

        try:
            link4 = "ivytech.edu" + link_list[3]
        except IndexError:
            link4 = ""

        meeting_page = "https://www.ivytech.edu/about-ivy-tech/college-operations/state-board-of-trustees/"  # noqa

        return [
            {"href": link1, "title": "Link 1"},
            {"href": link2, "title": "Link 2"},
            {"href": link3, "title": "Link 3"},
            {"href": link4, "title": "Link 4"},
            {"href": meeting_page, "title": "Meeting Page"},
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
