from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndPublicLibrarySpider(CityScrapersSpider):
    name = "ind_public_library"
    agency = "Indianapolis Public Library Board"
    timezone = "America/Detroit"
    start_urls = [
        "https://www.indypl.org/about-the-library/board-meeting-times-committees"
    ]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        count = 0
        for item in response.css("details div ul li"):
            if count < 15:
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
                count += 1
                yield meeting
            else:
                break

    def _parse_title(self, item):
        """Parse or generate meeting title."""
        title = "Indianapolis Public Library Board Of Trustees"
        return title

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        return ""

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        text = item.css("::text").get()
        start_date = text.split(" ", 2)[0] + " " + text.split(" ", 2)[1]
        dt_obj = start_date + " " + "14:30:00"
        return parser().parse(dt_obj)

    def _parse_end(self, item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        text = item.css("::text").get().strip()
        return (
            "Meetings are usually held at 6:30pm on the fourth Monday of the month, please check if the time has changed as specified in the following: "  # noqa
            + text
        )

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        location = item.css("::text").get().strip()
        return {"address": "", "name": location.split(" ", 3)[-1]}

    def _parse_links(self, item):
        """Parse or generate links."""
        livestream_link = item.css("a::attr(href)").get()
        locations = "https://www.indypl.org/locations"
        return [
            {"href": livestream_link, "title": "Link to livestream"},
            {"href": locations, "title": "Library locations"},
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
