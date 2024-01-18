from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndIndygoFinanceSpider(CityScrapersSpider):
    name = "ind_indygo_finance"
    agency = "Indianapolis Indygo Finance Committee"
    timezone = "America/Detroit"
    start_urls = ["https://www.indygo.net/about-indygo/board-of-directors/"]
    location = {
        "name": "Administrative Office - Board Room",
        "address": "1501 W. Washington St. Indianapolis, IN 46222",
    }
    links = [
        {
            "href": "https://www.indygo.net/about-indygo/board-of-directors/",
            "title": "Meeting Page",
        },
        {
            "href": "https://public.onboardmeetings.com/Group/HrdLpC4rmFdYrgplGJZm82TtkS14OCvw7QLcFFPpPrIA/PBtWHdxtJt6XgVphYPHNTSsJFC992FZbLhKOoPeFrjsA",  # noqa
            "title": "Past Finance Committee packets",
        },
    ]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        meeting_section = response.css(".content-section:nth-child(6)")
        section_title = meeting_section.css("h2::text").get()
        meeting_year = section_title.split(" ")[0]
        meeting_time = (
            (response.css(".content-section:nth-child(6) p strong::text").get())
            .split(":", 1)[1]
            .strip()
        )

        for date_item in meeting_section.css("ul li"):
            meeting = Meeting(
                title="IndyGo Finance Committee",
                description="",
                classification=BOARD,
                start=self._parse_start(date_item, meeting_year, meeting_time),
                end=None,
                all_day=False,
                time_notes="",
                location=self.location,
                links=self.links,
                source=response.url,
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_start(self, date_item, meeting_year, meeting_time):
        """Parse start datetime as a naive datetime object."""
        meeting_date = (date_item.css("::text").get()).split("-")[0]
        return parser().parse(meeting_date + " " + meeting_year + " " + meeting_time)
