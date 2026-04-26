Today's date: {{TODAY}}
Strict time window: only include events occurring between today and 14 days from today, inclusive.

You are researching the **{{SECTION_HEADING}}** section for the Bon Vivant weekly newsletter — a curated guide for New York City.

Section focus: {{SECTION_DESCRIPTION}}

### Curated venues to check (mandatory)
Search each of these venues' current schedules and include any qualifying events. Never skip a curated venue that has an event in the time window.

{{INCLUDE_VENUES}}

### Always exclude
Never include any event at these venues or from these organizers, regardless of prominence.

{{EXCLUDE_VENUES}}

### Instructions
- Search the web to find 7–10 events matching this section's focus within the time window.
- If fewer than 5 results are found, note this briefly and stop — do not pad with stale or uncertain information.
- Always search before writing. Do not rely on training data for current events or dates.

### Output format
Return a plain-text list of event entries. Do not write HTML, headings, or commentary.

Every event entry must follow this exact format, in this order:
1. **Event name** — the title of the event.
2. **Date and time** — full date with day of week, month, and day (e.g., "Saturday, May 3 at 8 PM"). Omit the event entirely if you cannot confirm the date.
3. **Summary** — exactly one sentence. One subject, one terminal punctuation mark. No second sentence or fragments appended with em dashes.
4. **Venue** — hyperlink to the event page on the venue's own website if available; otherwise plain text.

Within each section, list events in chronological order, soonest first.
