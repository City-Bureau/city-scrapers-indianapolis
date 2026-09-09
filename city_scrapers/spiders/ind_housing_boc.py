import re
from datetime import datetime

import scrapy
from city_scrapers_core.constants import BOARD, CANCELLED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class IndHousingBocSpider(CityScrapersSpider):
    name = "ind_housing_boc"
    agency = "Indianapolis Housing Agency Board of Commissioners"
    timezone = "America/Detroit"
    start_urls = [
        "https://www.indyhousing.org/calendar",
        "https://www.indyhousing.org/news-archives/filters/"
        "Y2F0ZWdvcnl+MDY2MzcwMDA2MWFhMTFmMDk5OTlkOWNkYTk1YzExMjM=/=desc/1",
    ]

    LOCATION_NAME = "Indianapolis Housing Agency"

    # Matches e.g. "February 17, 2026, at 1:00 PM" (ignores leading weekday)
    ARCHIVE_DATETIME_RE = re.compile(
        r"([A-Z][a-z]+ \d{1,2},\s*\d{4}),?\s*at\s*([\d:]+\s*[APMapm\.]{2,4})"
    )
    ADDRESS_RE = re.compile(
        r"\d{1,5}(?!\s*[APap][Mm]\b)\s+[A-Za-z0-9.,#\s]+?,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?"  # noqa
    )
    # Matches the archive pagination URL suffix (e.g. "/=desc/1")
    ARCHIVE_PAGE_RE = re.compile(r"/=desc/(\d+)$")

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_start)

    def parse_start(self, response):
        """
        Entry point for both the upcoming-meetings calendar and the
        past-meetings archive listing. Each meeting link is followed to its
        detail page, where the actual Meeting item is built and yielded.
        """
        if response.css("#listItems"):
            yield from self._parse_upcoming_list(response)
        elif response.css("#listWithImages"):
            yield from self._parse_archive_list(response)
        else:
            self.logger.warning(
                "Unrecognized listing page template at %s — neither "
                "#listItems nor #listWithImages found. Site markup may "
                "have changed.",
                response.url,
            )

    def _parse_upcoming_list(self, response):
        """Follow each upcoming-meeting link on the /calendar page."""
        for item in response.css("#listItems a.eventContainer"):
            href = item.attrib.get("href")
            if href:
                yield response.follow(href, callback=self.parse)

    def _parse_archive_list(self, response):
        """Follow each past-meeting link on the news-archives listing page,
        and continue on to the next archive page if one exists."""
        items = response.css("#listWithImages a.listItemWithImage")

        page_match = self.ARCHIVE_PAGE_RE.search(response.url)
        current_page = int(page_match.group(1)) if page_match else None

        if not items:
            if current_page is None or current_page == 1:
                self.logger.warning(
                    "No meeting links found on archive listing page %s — "
                    "selector may be stale.",
                    response.url,
                )
            return

        for item in items:
            href = item.attrib.get("href")
            if href:
                yield response.follow(href, callback=self.parse)

        # The archive URL encodes its page number directly (".../=desc/1",
        # ".../=desc/2", ...). Since this page had results, request the next
        # page number; if it comes back empty we'll stop there.
        if page_match:
            next_url = self.ARCHIVE_PAGE_RE.sub(
                f"/=desc/{current_page + 1}", response.url
            )
            yield response.follow(next_url, callback=self.parse_start)
        else:
            self.logger.warning(
                "Could not find a page number in archive URL %s — unable "
                "to compute the next page.",
                response.url,
            )

    def parse(self, response):
        """
        Build a Meeting item from an individual meeting detail page. Detects
        and handles both the upcoming-meeting template (/calendar/...) and
        the past-meeting template (/news-archives/...).
        """
        date_hook_text = " ".join(
            response.css(".css_hook_date").css("*::text").getall()
        )
        is_upcoming = "Start Date" in date_hook_text
        if is_upcoming:
            parsed = self._parse_upcoming_detail(response)
        else:
            parsed = self._parse_archive_detail(response)

        if parsed is None or parsed["start"] is None:
            self.logger.warning(
                "Could not parse a start datetime for detail page %s — "
                "skipping this meeting.",
                response.url,
            )
            return

        meeting = Meeting(
            title=parsed["title"],
            description="",
            classification=BOARD,
            start=parsed["start"],
            end=None,
            all_day=False,
            time_notes="",
            location=parsed["location"],
            links=self._parse_links(response, is_upcoming),
            source=response.url,
        )

        if parsed.get("no_meeting"):
            meeting["status"] = CANCELLED
        else:
            meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)

        yield meeting

    def _no_meeting_flag(self, raw_title):
        """Detect whether the page indicates there's no actual meeting
        (e.g. a recess notice), shared by both templates."""
        return "no board meeting" in (raw_title or "").lower()

    def _parse_location(self, address):
        """Build the location dict shared by both templates."""
        return {"name": self.LOCATION_NAME, "address": address}

    def _parse_meeting_fields(self, title, start, location, no_meeting):
        """Assemble the intermediate dict both detail parsers return, so
        `parse()` can build the Meeting the same way"""
        return {
            "title": title,
            "start": start,
            "location": location,
            "no_meeting": no_meeting,
        }

    def _parse_upcoming_detail(self, response):
        """Parse the upcoming-meeting detail page template."""
        raw_title = response.css("h1.ptitles::text").get() or response.css(
            "title::text"
        ).get("")
        title = self._clean_title(raw_title)
        no_meeting = self._no_meeting_flag(raw_title)

        start_date = None
        for date_div in response.css(".css_hook_date"):
            text = " ".join(date_div.css("*::text").getall())
            match = re.search(r"Start Date:\s*([\d/]+)", text)
            if match:
                start_date = match.group(1)
                break

        time_text = " ".join(response.css(".css_hook_time").css("*::text").getall())
        time_match = re.search(r"Start Time:\s*([\d:]+\s*[apAP][mM])", time_text)
        start_time = time_match.group(1) if time_match else None

        start = None
        if start_date and start_time:
            try:
                start = datetime.strptime(
                    f"{start_date} {start_time}", "%m/%d/%Y %I:%M %p"
                )
            except ValueError:
                start = None
        elif start_date:
            # No start-time widget on the page (e.g. a recess / no-meeting
            # notice) — fall back to the date alone.
            try:
                start = datetime.strptime(start_date, "%m/%d/%Y")
            except ValueError:
                start = None

        address = ""
        if not no_meeting:
            location_text = " ".join(
                response.css(".css_hook_longtext p::text").getall()
            )
            if "|" in location_text:
                address = location_text.split("|", 1)[1].strip()

        return self._parse_meeting_fields(
            title, start, self._parse_location(address), no_meeting
        )

    def _parse_archive_detail(self, response):
        """Parse the past-meeting (news-archive) detail page template."""
        raw_title = response.css("h1.ptitles::text").get("")
        title = self._clean_title(raw_title)
        no_meeting = self._no_meeting_flag(raw_title)

        paragraphs = response.css(".css_hook_longtext p")
        info_text = (
            " ".join(paragraphs[:1].css("*::text").getall()) if paragraphs else ""
        )

        start = None
        match = self.ARCHIVE_DATETIME_RE.search(info_text)
        if match:
            date_part, time_part = match.groups()
            try:
                start = datetime.strptime(
                    f"{date_part} {time_part}".replace(".", ""),
                    "%B %d, %Y %I:%M %p",
                )
            except ValueError:
                start = None

        address = ""
        if not no_meeting:
            addr_match = self.ADDRESS_RE.search(info_text)
            if addr_match:
                address = addr_match.group(0).strip()

        return self._parse_meeting_fields(
            title, start, self._parse_location(address), no_meeting
        )

    def _clean_title(self, raw_title):
        """Strip trailing ' | <date>' and site-name suffixes from a title."""
        return (raw_title or "").split("|")[0].strip()

    def _parse_links(self, response, is_upcoming):
        """Parse or generate links.

        The meeting's own detail page (reached via the href followed from
        the calendar/archive listing) is used as the attachment link.
        """
        if is_upcoming:
            return []
        return [{"href": response.url, "title": "Meeting Attachment"}]
