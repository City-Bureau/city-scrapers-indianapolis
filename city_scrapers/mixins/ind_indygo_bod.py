import re

import scrapy
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parser


class IndIndygoBodSpiderMeta(type):
    """
    Metaclass that enforces required static variables on generated spiders.
    """

    def __init__(cls, name, bases, namespace):
        if name == "IndIndygoBodSpiderMixin":
            super().__init__(name, bases, namespace)
            return

        if any(
            getattr(base, "__name__", "") == "IndIndygoBodSpiderMixin" for base in bases
        ):
            required_static_vars = [
                "agency",
                "name",
                "title",
                "section_heading_match",
            ]

            missing_vars = [
                variable
                for variable in required_static_vars
                if variable not in namespace
            ]

            if missing_vars:
                missing_vars_str = ", ".join(missing_vars)

                raise NotImplementedError(
                    f"{name} must define the following static variable(s): "
                    f"{missing_vars_str}."
                )

        super().__init__(name, bases, namespace)


class IndIndygoBodSpiderMixin(
    CityScrapersSpider,
    metaclass=IndIndygoBodSpiderMeta,
):
    """
    Shared implementation for the IndyGo Board and committee spiders.
    """

    name = None
    agency = None
    title = None
    classification = BOARD
    section_heading_match = None
    links = []

    _FALLBACK_TIME_NOTES = "Check meeting attachments for a more accurate location."

    _LOCATION_RE = re.compile(r"held at (?P<address>.+?) in the (?P<name>.+?)\.")

    #: Facebook/fb.watch videos require a login to play, so skip them.
    _FACEBOOK_LINK_RE = re.compile(r"^https?://(www\.)?(facebook\.com|fb\.watch)/")

    #: Catches broken `href`s where an editor pasted the link text itself
    #: (e.g. "http://Finance Committee Meeting") instead of a real URL -
    #: no real URL contains a literal space.
    _MALFORMED_HREF_RE = re.compile(r"\s")

    board_reports_container_selector = None

    video_archive_url = "https://www.indygo.net/board-meeting-media-archives/"

    video_archive_pattern = None

    _MONTH_NAMES = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )

    #: Strips the parts of a section heading editors tend to vary - the
    #: year, "&" vs "and", case, punctuation - so "2026 Governance and
    #: Audit Committee" and "Governance & Audit Committee" compare equal.
    _HEADING_NORMALIZE_RE = re.compile(r"\band\b|[^a-z ]")

    #: Extra `?year=<meeting_year + offset>` requests against a committee's
    #: OnBoard listings page. Each such response always includes the
    #: requested year plus the year before it, so offset -1 sweeps up
    #: `meeting_year - 1` and `- 2`, and offset +1 sweeps up
    #: `meeting_year + 1` - net effect: 2 years back, 1 forward.
    _EXTRA_LISTING_YEAR_OFFSETS = (-1, 1)

    timezone = "America/Indiana/Indianapolis"

    start_urls = ["https://www.indygo.net/about-indygo/board-of-directors/"]

    custom_settings = {"ROBOTSTXT_OBEY": False, "FEED_EXPORT_ENCODING": "utf-8"}

    def parse(self, response):
        """Parse this spider's section, then backfill any `historical_snapshots`."""
        yield from self._parse_schedule_page(response)

    def _parse_schedule_page(self, response):
        """Parse meetings from a board page's schedule section."""
        # Passed down through cb_kwargs rather than stored on `self`: live
        # page and snapshot chains run concurrently, so spider-wide state
        # would let one response's location leak onto another's meetings.
        venue = self._parse_location_and_time_notes(response)

        heading = self._find_section_heading(response)
        if heading is None:
            self.logger.warning(
                "Could not find a section heading matching %r for %s",
                self.section_heading_match,
                self.agency,
            )
            return

        meeting_year, raw_meeting_time, dates_list, listings_href = self._parse_section(
            heading, response
        )

        if meeting_year is None:
            self.logger.warning(
                "Could not find a meeting year in the %r section for %s",
                self.section_heading_match,
                self.agency,
            )
            return

        if not raw_meeting_time:
            self.logger.warning(
                "Could not find a meeting time for %s",
                self.agency,
            )
            return

        if dates_list is None:
            self.logger.warning(
                "Could not find meeting dates for %s",
                self.agency,
            )
            return

        meeting_time = self._parse_meeting_time(raw_meeting_time)

        starts = self._parse_starts(dates_list, meeting_year, meeting_time, response)

        board_reports_by_month = (
            self._parse_board_reports(response)
            if self.board_reports_container_selector
            else None
        )

        if self.video_archive_pattern:
            yield scrapy.Request(
                self.video_archive_url,
                callback=self._parse_video_archive_and_continue,
                errback=self._continue_without_video_archive,
                # The live page and any same-design historical snapshot both
                # fetch this same URL - without this, Scrapy's dupe filter
                # silently drops every request after the first, dropping
                # that entire snapshot's meetings with no warning logged.
                dont_filter=True,
                cb_kwargs={
                    "starts": starts,
                    "source": response.url,
                    "board_reports_by_month": board_reports_by_month,
                    "listings_href": listings_href,
                    "meeting_year": meeting_year,
                    "meeting_time": meeting_time,
                    "venue": venue,
                },
            )
        else:
            yield from self._continue_parsing(
                starts,
                response.url,
                listings_href,
                meeting_year,
                meeting_time,
                board_reports_by_month,
                venue=venue,
            )

    def _parse_starts(self, dates_list, meeting_year, meeting_time, response):
        """
        Build `(start, title, document_href)` tuples for a schedule list,
        skipping (and logging) any item that won't parse, so one editor
        typo doesn't cost the whole section.
        """
        starts = []

        for date_item in dates_list.css("li"):
            try:
                start = self._parse_start(date_item, meeting_year, meeting_time)
            except (ValueError, OverflowError) as exc:
                self.logger.warning(
                    "Skipping unparseable schedule item on %s: %s", response.url, exc
                )
                continue

            starts.append(
                (
                    start,
                    self._parse_title(date_item),
                    self._parse_document_link(date_item, response),
                )
            )

        return starts

    # -- Errbacks -------------------------------------------------------
    #
    # Meetings are only yielded at the end of the request chain, so a failed
    # enrichment request (video archive, OnBoard, a later snapshot) must not
    # take the already-parsed schedule down with it. Each errback carries on
    # with the same cb_kwargs, minus whatever the failed request would have
    # added.

    def _continue_without_video_archive(self, failure):
        self.logger.warning(
            "Video archive request failed (%s); continuing without video links",
            failure.request.url,
        )
        yield from self._continue_parsing(**failure.request.cb_kwargs)

    def _continue_without_listings(self, failure):
        self.logger.warning(
            "Meeting listings request failed (%s); continuing without listings",
            failure.request.url,
        )
        yield from self._continue_parsing(
            **{**failure.request.cb_kwargs, "listings_href": None}
        )

    def _skip_extra_listing_year(self, failure):
        self.logger.warning(
            "Extra listing year request failed (%s); skipping that year",
            failure.request.url,
        )
        yield from self._fetch_extra_listing_years(**failure.request.cb_kwargs)

    def _parse_location_and_time_notes(self, response):
        location = self._parse_location(response)
        if location:
            return location, ""

        return {"name": "", "address": ""}, self._FALLBACK_TIME_NOTES

    def _parse_location(self, response):
        headings = response.xpath(
            '//h2[normalize-space(text())="Attend a Board Meeting"]'
        )
        if not headings:
            return None

        paragraphs = headings[0].xpath("following-sibling::p[1]")
        if not paragraphs:
            return None

        paragraph_text = "".join(paragraphs.css("::text").getall()).strip()

        match = self._LOCATION_RE.search(paragraph_text)
        if not match:
            return None

        address = match.group("address").replace(".", "").strip()
        name = match.group("name")
        name = name.replace("located in our", "-")
        name = name.replace("“", "'").replace("”", "'").replace('"', "'")
        name = re.sub(r"\s+", " ", name).strip()

        if not address or not name:
            return None

        return {"name": name, "address": f"{address}, Indianapolis, IN 46235"}

    def _parse_video_archive_and_continue(
        self,
        response,
        starts,
        source,
        board_reports_by_month,
        listings_href,
        meeting_year,
        meeting_time,
        venue=None,
    ):
        video_link_by_month = self._parse_video_archive(response)
        yield from self._continue_parsing(
            starts,
            source,
            listings_href,
            meeting_year,
            meeting_time,
            board_reports_by_month,
            video_link_by_month,
            venue=venue,
        )

    def _continue_parsing(
        self,
        starts,
        source,
        listings_href,
        meeting_year,
        meeting_time,
        board_reports_by_month=None,
        video_link_by_month=None,
        venue=None,
    ):
        if listings_href:
            yield scrapy.Request(
                listings_href,
                callback=self._parse_meeting_listings_and_build,
                errback=self._continue_without_listings,
                cb_kwargs={
                    "starts": starts,
                    "source": source,
                    "listings_href": listings_href,
                    "meeting_year": meeting_year,
                    "meeting_time": meeting_time,
                    "board_reports_by_month": board_reports_by_month,
                    "video_link_by_month": video_link_by_month,
                    "venue": venue,
                },
            )
        else:
            for start, title, document_href in starts:
                links = self._resolve_links(
                    start,
                    document_href=document_href,
                    board_reports_by_month=board_reports_by_month,
                    video_link_by_month=video_link_by_month,
                )
                yield self._build_meeting(start, title, links, source, venue)

    def _build_meeting(self, start, title, links, source, venue=None):
        location, time_notes = venue or (
            {"name": "", "address": ""},
            self._FALLBACK_TIME_NOTES,
        )

        meeting = Meeting(
            title=title,
            description="",
            classification=self.classification,
            start=start,
            end=None,
            all_day=False,
            time_notes=time_notes,
            location=location,
            links=links,
            source=source,
        )

        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)

        return meeting

    def _parse_meeting_listings_and_build(
        self,
        response,
        starts,
        source,
        listings_href,
        meeting_year,
        meeting_time,
        board_reports_by_month=None,
        video_link_by_month=None,
        venue=None,
    ):
        """Match current-year meetings to the OnBoard listing, then fetch extra years."""  # noqa
        meeting_link_by_date, _past_dates_by_year = self._parse_meeting_listings(
            response, meeting_year
        )

        yield from self._fetch_extra_listing_years(
            list(self._EXTRA_LISTING_YEAR_OFFSETS),
            starts=starts,
            source=source,
            listings_href=listings_href,
            meeting_year=meeting_year,
            meeting_time=meeting_time,
            meeting_link_by_date=meeting_link_by_date,
            extra_dates_by_year={},
            board_reports_by_month=board_reports_by_month,
            video_link_by_month=video_link_by_month,
            venue=venue,
        )

    def _fetch_extra_listing_years(
        self,
        remaining_offsets,
        starts,
        source,
        listings_href,
        meeting_year,
        meeting_time,
        meeting_link_by_date,
        extra_dates_by_year,
        board_reports_by_month=None,
        video_link_by_month=None,
        venue=None,
    ):
        if not remaining_offsets:
            all_starts = starts + self._parse_past_starts(
                extra_dates_by_year, meeting_time
            )
            for start, title, document_href in all_starts:
                links = self._resolve_links(
                    start,
                    document_href=document_href,
                    listings_href=listings_href,
                    meeting_link_by_date=meeting_link_by_date,
                    board_reports_by_month=board_reports_by_month,
                    video_link_by_month=video_link_by_month,
                )
                yield self._build_meeting(start, title, links, source, venue)
            return

        offset, remaining_offsets = remaining_offsets[0], remaining_offsets[1:]
        separator = "&" if "?" in listings_href else "?"
        year_url = f"{listings_href}{separator}year={int(meeting_year) + offset}"

        yield scrapy.Request(
            year_url,
            callback=self._parse_extra_listing_year_and_continue,
            errback=self._skip_extra_listing_year,
            cb_kwargs={
                "remaining_offsets": remaining_offsets,
                "starts": starts,
                "source": source,
                "listings_href": listings_href,
                "meeting_year": meeting_year,
                "meeting_time": meeting_time,
                "meeting_link_by_date": meeting_link_by_date,
                "extra_dates_by_year": extra_dates_by_year,
                "board_reports_by_month": board_reports_by_month,
                "video_link_by_month": video_link_by_month,
                "venue": venue,
            },
        )

    def _parse_extra_listing_year_and_continue(
        self,
        response,
        remaining_offsets,
        starts,
        source,
        listings_href,
        meeting_year,
        meeting_time,
        meeting_link_by_date,
        extra_dates_by_year,
        board_reports_by_month=None,
        video_link_by_month=None,
        venue=None,
    ):
        new_link_by_date, new_dates_by_year = self._parse_meeting_listings(
            response, meeting_year
        )

        meeting_link_by_date = {**meeting_link_by_date, **new_link_by_date}

        extra_dates_by_year = dict(extra_dates_by_year)
        for year, dates in new_dates_by_year.items():
            # First offset to find a year wins - guards against OnBoard's
            # fallback view re-reporting a year we already have.
            extra_dates_by_year.setdefault(year, dates)

        yield from self._fetch_extra_listing_years(
            remaining_offsets,
            starts=starts,
            source=source,
            listings_href=listings_href,
            meeting_year=meeting_year,
            meeting_time=meeting_time,
            meeting_link_by_date=meeting_link_by_date,
            extra_dates_by_year=extra_dates_by_year,
            board_reports_by_month=board_reports_by_month,
            video_link_by_month=video_link_by_month,
            venue=venue,
        )

    def _resolve_links(
        self,
        start,
        document_href=None,
        listings_href=None,
        meeting_link_by_date=None,
        board_reports_by_month=None,
        video_link_by_month=None,
    ):
        """Add a link only once a document for this exact meeting exists."""
        links = [dict(link) for link in self.links]

        if document_href:
            links.append({"href": document_href, "title": "Agenda"})

        if listings_href:
            date_key = (str(start.year), start.strftime("%b"), start.day)
            self._append_link(links, meeting_link_by_date, date_key, "Meeting Listing")

        if board_reports_by_month:
            month_key = (str(start.year), start.strftime("%B"))
            self._append_link(links, board_reports_by_month, month_key, "Board Report")

        if video_link_by_month:
            month_key = (str(start.year), start.strftime("%B"))
            self._append_link(links, video_link_by_month, month_key, "Video")

        return links

    def _append_link(self, links, mapping, key, title):
        """
        Add a link and consume it, so it's attached to only one meeting.

        This matters for the month-keyed maps (Board Reports, Video): when a
        month has two meetings - e.g. the July budget introduction and the
        late-July public hearing - only the first in `starts` order gets
        that month's report/video. Date-keyed listing links are unique anyway.
        """
        href = (mapping or {}).pop(key, None)
        if href:
            links.append({"href": href, "title": title})

    def _is_facebook_link(self, href):
        return bool(self._FACEBOOK_LINK_RE.match(href))

    def _is_malformed_href(self, href):
        return bool(self._MALFORMED_HREF_RE.search(href))

    def _parse_board_reports(self, response):
        """
        Walk the "Board Reports" accordion and return a
        `{(year, month_name): report_url}` mapping of each month's report.
        """
        board_reports_by_month = {}
        month_pattern = "|".join(self._MONTH_NAMES)

        accordion_items = response.css(
            f"{self.board_reports_container_selector} .rc-accordion-item"
        )

        for item in accordion_items:
            heading_text = item.css(".rc-accordion-button-text::text").get()
            if not heading_text:
                continue

            year_match = re.search(r"\b\d{4}\b", heading_text)
            if not year_match:
                continue

            year = year_match.group()

            for link in item.css(".rc-accordion-body ul.wp-block-list > li > a"):
                link_text = "".join(link.css("::text").getall()).strip()
                month_match = re.match(
                    rf"({month_pattern})\s+{year}\s+Board\s+(?:Meeting|Report)\b",
                    link_text,
                )
                if not month_match:
                    continue

                href = link.attrib.get("href")
                if not href:
                    continue

                board_reports_by_month[(year, month_match.group(1))] = response.urljoin(
                    href
                )

        return board_reports_by_month

    def _parse_video_archive(self, response):
        video_link_by_month = {}

        for year_item in response.css(".rc-block--accordion .rc-accordion-item"):
            year = year_item.css(".rc-accordion-button-text::text").get()
            if not year:
                continue

            current_month = None

            for child in year_item.css(".rc-accordion-content").xpath("./*"):
                tag = child.root.tag

                if tag == "p":
                    current_month = "".join(child.css("::text").getall()).strip()
                    continue

                if tag != "ul" or not current_month:
                    continue

                for link in child.css("li > a"):
                    link_text = "".join(link.css("::text").getall()).strip()
                    if not re.match(
                        self.video_archive_pattern, link_text, re.IGNORECASE
                    ):
                        continue

                    href = link.attrib.get("href")
                    if (
                        not href
                        or self._is_facebook_link(href)
                        or self._is_malformed_href(href)
                    ):
                        continue

                    video_link_by_month[(year, current_month)] = response.urljoin(href)

        return video_link_by_month

    def _parse_meeting_listings(self, response, meeting_year):
        """
        Return `{(year, month_abbr, day): meeting_url}` for every listed
        meeting, plus `{year: [(month_abbr, day), ...]}` for any other
        years also shown on the page.
        """
        meeting_link_by_date = {}
        past_dates_by_year = {}
        current_year = None

        nodes = response.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), '
            '" year-text ") or '
            'contains(concat(" ", normalize-space(@class), " "), '
            '" year-meetings ")]'
        )

        for node in nodes:
            classes = node.attrib.get("class", "").split()

            if "year-text" in classes:
                current_year = node.css("h3::text").get()
                continue

            if current_year is None:
                continue

            for day_item in node.css(".meeting-day-item"):
                day_label = day_item.css(".day-label::text").get()
                if not day_label:
                    continue

                month_abbr, _, day_str = day_label.strip().partition(" ")
                if not day_str.isdigit():
                    continue

                href = day_item.css("a.meeting-link::attr(href)").get()
                if not href:
                    continue

                date_key = (current_year, month_abbr, int(day_str))
                meeting_link_by_date[date_key] = response.urljoin(href)

                if current_year != meeting_year:
                    past_dates_by_year.setdefault(current_year, []).append(
                        (month_abbr, int(day_str))
                    )

        return meeting_link_by_date, past_dates_by_year

    def _parse_past_starts(self, past_dates_by_year, meeting_time):
        """
        Build `(start, title, document_href)` tuples for meetings found only
        on the OnBoard listing, using the same recurring meeting time as the
        current year. There's no source element to pull a document link
        from, so `document_href` is always `None`.
        """
        past_starts = []

        for year, dates in past_dates_by_year.items():
            for month_abbr, day in dates:
                start = parser().parse(f"{month_abbr} {day} {year} {meeting_time}")
                past_starts.append((start, self.title, None))

        return sorted(past_starts, key=lambda item: item[0])

    def _normalize_heading(self, text):
        text = self._HEADING_NORMALIZE_RE.sub(" ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    def _find_section_heading(self, response):
        """
        Find this spider's `h2` by its text rather than by a layout class,
        which is what a redesign is most likely to rename.
        """
        target = self._normalize_heading(self.section_heading_match)

        for heading in response.xpath("//h2"):
            heading_text = " ".join(heading.css("::text").getall())
            if target in self._normalize_heading(heading_text):
                return heading

        return None

    def _parse_section(self, heading, response):
        """
        Read the section under `heading`: its following siblings up to the
        next h2/h3. Works on both page designs - on the old one each h2
        sits in its own `div.content-section`, so its siblings are exactly
        that section's contents.
        """
        heading_text = " ".join(heading.css("::text").getall()).strip()
        try:
            meeting_year = self._parse_meeting_year(heading_text)
        except ValueError as exc:
            self.logger.warning("%s", exc)
            return None, None, None, None

        raw_meeting_time = None
        dates_list = None
        listings_href = None

        for child in heading.xpath("following-sibling::*"):
            tag = child.root.tag

            if tag in ("h2", "h3"):
                break

            if tag == "p":
                strong_text = child.css("strong::text").get()
                link_text = child.css("a::text").get() or ""
                if strong_text and "meeting time" in strong_text.lower():
                    raw_meeting_time = strong_text
                elif "click here" in link_text.lower():
                    href = child.css("a::attr(href)").get()
                    if href:
                        listings_href = response.urljoin(href)
            elif tag == "ul" and dates_list is None:
                # First list only, so a following block can't bleed in.
                dates_list = child

        return meeting_year, raw_meeting_time, dates_list, listings_href

    def _parse_meeting_year(self, section_title):
        """Parse the four-digit year from a section heading like "2026 ...Meetings"."""
        year_match = re.search(r"\b\d{4}\b", section_title)

        if not year_match:
            raise ValueError(
                f"Could not find meeting year in section title: {section_title!r}"
            )

        return year_match.group()

    def _parse_meeting_time(self, raw_time):
        """Strip the field label and trailing timezone abbreviation."""
        if ":" in raw_time:
            time_string = raw_time.split(":", 1)[1]
        else:
            time_string = raw_time

        return re.sub(
            r"\s*(?:EST|EDT)\s*$",
            "",
            time_string,
            flags=re.IGNORECASE,
        ).strip()

    #: Matches the leading "Weekday, Month Day[st|nd|rd|th]" part of a
    #: schedule item, ignoring any annotation after it (dash, colon, etc).
    _DATE_PREFIX_RE = re.compile(r"^[A-Za-z]+,\s*[A-Za-z.]+\s*\d{1,2}(?:st|nd|rd|th)?")

    def _parse_start(self, date_item, meeting_year, meeting_time):
        """
        Parse the meeting start as a naive datetime object.

        E.g. "Thursday, Jan. 15" or "Thursday, July 16 – Budget Introduced".
        """
        raw_date = " ".join(date_item.css("::text").getall()).strip()

        date_match = self._DATE_PREFIX_RE.match(raw_date)
        if not date_match:
            raise ValueError(f"Could not parse a date from: {raw_date!r}")

        meeting_date = date_match.group()

        return parser().parse(f"{meeting_date} {meeting_year} {meeting_time}")

    def _parse_title(self, date_item):
        raw_date = " ".join(date_item.css("::text").getall()).strip()

        date_match = self._DATE_PREFIX_RE.match(raw_date)
        remainder = raw_date[date_match.end() :] if date_match else raw_date

        description_match = re.match(r"\s*[-–]\s*(.+)", remainder)
        if description_match:
            return f"{self.title} – {description_match.group(1).strip()}"

        return self.title

    def _parse_document_link(self, date_item, response):
        """A date can itself be a link to a document, e.g. a meeting agenda."""
        href = date_item.css("a::attr(href)").get()
        return response.urljoin(href) if href else None
