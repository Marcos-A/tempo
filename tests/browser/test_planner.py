"""The internship planner's behaviour in a real browser.

Much of the planner lives in the page's script, which the other tests never
run: how the form's choices reach the calculation, how hand-set hours are
kept, and a second copy of rules the server also has. Keep this suite small:
add a test for a bug that got through, or for a rule that exists in both places.

The plans use dates in 2026-27, whose school periods are seeded in conftest.py.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright")

# 400 h at 4 h a day from Monday 9 November 2026, around every school period.
START = "09/11/2026"
HOURS = 400
END = "27/04/2027"
EASTER_BREAK = "Vacances de Setmana Santa"
ONE_DAY_DROPPED = "S'han tret les hores canviades a mà d'1 dia, que ara és sense pràctiques."


@pytest.fixture()
def plan(planner):
    planner.fill(start=START, hours=HOURS, end=END)
    return planner


# A day that becomes a day without internship loses its hand-set hours.


def test_adding_a_day_off_replaces_its_hand_set_hours(plan):
    plan.set_day("2026-11-17", 6)
    plan.expect_day("2026-11-17", "override", "6h")

    plan.add_day_off("17/11/2026")

    plan.expect_day("2026-11-17", "holiday", "–")
    plan.expect_end("28/04/2027")
    plan.expect_changed_days(0)
    plan.expect_note(ONE_DAY_DROPPED)


def test_ticking_a_period_replaces_the_hand_set_hours_inside_it(plan):
    plan.period(EASTER_BREAK).uncheck()
    plan.expect_end("19/04/2027")
    plan.set_day("2027-03-23", 6)
    plan.set_day("2027-03-24", 6)
    plan.expect_changed_days(2)

    plan.period(EASTER_BREAK).check()

    plan.expect_day("2027-03-23", "holiday", "–")
    plan.expect_day("2027-03-24", "holiday", "–")
    plan.expect_end(END)
    plan.expect_changed_days(0)
    plan.expect_note("S'han tret les hores canviades a mà de 2 dies, que ara són sense pràctiques.")


def test_ticking_a_fixed_holiday_replaces_its_hand_set_hours(plan):
    plan.fixed_holiday("2026-12-08").uncheck()
    plan.expect_end("26/04/2027")
    plan.set_day("2026-12-08", 6)
    plan.expect_day("2026-12-08", "override", "6h")

    plan.fixed_holiday("2026-12-08").check()

    plan.expect_day("2026-12-08", "holiday", "–")
    plan.expect_end(END)
    plan.expect_note(ONE_DAY_DROPPED)


def test_mark_all_replaces_the_hand_set_hours_inside_the_periods(plan):
    plan.page.locator('[data-toggle-periods="off"]').click()
    plan.expect_day("2027-03-23", "working", "4h")
    plan.set_day("2027-03-23", 6)
    plan.expect_day("2027-03-23", "override", "6h")

    plan.page.locator('[data-toggle-periods="on"]').click()

    plan.expect_day("2027-03-23", "holiday", "–")
    plan.expect_end(END)
    plan.expect_note(ONE_DAY_DROPPED)


def test_hours_set_on_a_day_off_afterwards_stay(plan):
    plan.set_day("2027-03-23", 4)
    plan.expect_day("2027-03-23", "override", "4h")
    plan.expect_end("26/04/2027")
    plan.expect_note(None)

    # A change elsewhere in the section leaves them alone.
    plan.period("Lliure de febrer").uncheck()

    plan.expect_end("23/04/2027")
    plan.expect_day("2027-03-23", "override", "4h")
    plan.expect_note(None)


def test_hand_set_hours_on_other_days_stay_when_a_day_off_is_added(plan):
    plan.set_day("2026-11-17", 6)
    plan.set_day("2026-11-18", 6)
    plan.expect_changed_days(2)

    plan.add_day_off("17/11/2026")

    plan.expect_day("2026-11-17", "holiday", "–")
    plan.expect_day("2026-11-18", "override", "6h")
    plan.expect_changed_days(1)


# Every change in "Dies sense pràctiques" reaches the calendar.


def test_unticking_and_ticking_a_period_moves_the_end_date(plan):
    plan.expect_day("2027-03-23", "holiday", "–")

    plan.period(EASTER_BREAK).uncheck()
    plan.expect_day("2027-03-23", "working", "4h")
    plan.expect_end("19/04/2027")

    plan.period(EASTER_BREAK).check()
    plan.expect_day("2027-03-23", "holiday", "–")
    plan.expect_end(END)


def test_adding_and_removing_days_off_moves_the_end_date(plan):
    plan.add_day_off("02/02/2027", "04/02/2027")
    plan.expect_day("2027-02-03", "holiday", "–")
    plan.expect_end("03/05/2027")

    plan.remove_first_day_off()
    plan.expect_day("2027-02-03", "working", "4h")
    plan.expect_end(END)


def test_unmark_all_and_mark_all_move_the_end_date(plan):
    plan.page.locator('[data-toggle-periods="off"]').click()
    plan.expect_day("2027-03-23", "working", "4h")
    plan.expect_day("2026-12-08", "working", "4h")

    plan.page.locator('[data-toggle-periods="on"]').click()
    plan.expect_day("2027-03-23", "holiday", "–")
    plan.expect_day("2026-12-08", "holiday", "–")
    plan.expect_end(END)


# Options that change which days can take hours.


def test_including_august_gives_it_hours_and_moves_the_limit(planner):
    planner.fill(start="01/07/2027", hours=150, end="30/07/2027")
    planner.expect_hours("88 h / 150 h")

    planner.page.check("#include-august")

    planner.expect_end("23/08/2027")
    planner.expect_hours("150 h / 150 h")
    planner.expect_day("2027-08-03", "working", "4h")


def test_hours_set_in_august_wait_while_it_is_off(planner):
    planner.fill(start="01/07/2027", hours=150, end="30/07/2027")
    planner.page.check("#include-august")
    planner.expect_end("23/08/2027")
    planner.set_day("2027-08-03", 6)
    planner.expect_day("2027-08-03", "override", "6h")

    # The server refuses August hours, so sending them would hide the calendar.
    planner.page.uncheck("#include-august")
    planner.expect_end("30/07/2027")
    assert planner.day("2027-08-03").count() == 0

    planner.page.check("#include-august")
    planner.expect_day("2027-08-03", "override", "6h")


def test_a_start_date_in_august_needs_the_option(planner):
    planner.fill(start="01/07/2027", hours=100, end="30/07/2027")
    planner.page.fill("#start-date", "02/08/2027")
    planner.page.locator("#result-error", has_text="Inclou l'agost").wait_for()

    planner.page.check("#include-august")

    planner.expect_day("2027-08-03", "working", "4h")
    planner.page.locator("#result-error").wait_for(state="hidden")


def test_including_saturdays_uses_their_hours_and_brings_them_back(planner):
    planner.fill(start=START, hours=HOURS, end=END)
    planner.page.check("#include-saturdays")
    planner.page.select_option('[data-weekday-hours="5"]', "4")
    planner.expect_day("2026-11-14", "working", "4h")

    planner.page.uncheck("#include-saturdays")
    planner.expect_end(END)
    planner.expect_day("2026-11-14", "weekend", "–")

    planner.page.check("#include-saturdays")
    planner.expect_day("2026-11-14", "working", "4h")


# The page and the server each hold these rules, and must agree.


@pytest.mark.parametrize("modality", ["general", "intensiva"])
@pytest.mark.parametrize("include_august", [False, True])
@pytest.mark.parametrize("include_saturdays", [False, True])
def test_page_and_server_agree_on_the_limit_and_the_fixed_holidays(
    planner, fixed_holiday_labels, modality, include_august, include_saturdays
):
    # Far more hours than fit, so the calendar reaches the limit: a Monday, in the first state.
    planner.fill(start="06/09/2027", hours=3000, end="31/07/2028")
    if include_saturdays:
        planner.page.check("#include-saturdays")
    planner.choose_modality(modality)
    if include_august:
        planner.page.check("#include-august")
    # This last change tells the server's answer to the final state from any still on its way.
    with planner.page.expect_response(
        lambda response: response.url.endswith("/practiques/calcul")
        and json.loads(response.request.post_data)["weekday_minutes"]["0"] == 300
    ) as answer:
        planner.page.select_option('[data-weekday-hours="0"]', "5")
    data = answer.value.json()

    last_year = 2028 if modality == "general" else 2029
    last_day = f"31/08/{last_year}" if include_august else f"31/07/{last_year}"
    assert data["deadline_display"] == last_day

    server = {day["date"] for day in data["days"] if day["kind"] == "holiday" and day["label"] in fixed_holiday_labels}
    assert planner.listed_fixed_holidays() == server


# A saved calendar comes back as it was.


def test_saved_html_reopens_with_its_options_and_hand_set_hours(plan, tmp_path):
    plan.page.check("#include-august")
    plan.period(EASTER_BREAK).uncheck()
    plan.expect_end("19/04/2027")
    plan.set_day("2026-11-17", 6)
    plan.expect_day("2026-11-17", "override", "6h")
    # Hand-set hours on a day off must survive too: opening a plan is not a change to it.
    plan.set_day("2026-12-08", 3)
    plan.expect_day("2026-12-08", "override", "3h")
    saved_end = plan.page.locator("#summary-end").inner_text()

    plan.page.locator('[data-readonly-export="HTML"]').click()
    with plan.page.expect_download() as download:
        plan.page.locator("#export-readonly-confirm").click()
    saved = tmp_path / "calendari.html"
    download.value.save_as(saved)
    assert json.loads(saved.read_text().split('id="tempo-internship-plan">')[1].split("</script>")[0])["plan"]["include_august"] is True

    # Someone else, or another computer: no draft in this browser.
    other = plan.another_user()
    other.page.set_input_files("#plan-file", saved)

    other.expect_end(saved_end)
    other.expect_day("2026-11-17", "override", "6h")
    other.expect_day("2026-12-08", "override", "3h")
    other.expect_day("2027-03-23", "working", "4h")
    assert other.page.is_checked("#include-august")
    assert not other.period(EASTER_BREAK).is_checked()
    other.expect_note(None)
